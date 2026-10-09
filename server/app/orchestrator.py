# File: server/app/orchestrator.py
import asyncio
import inspect
import logging
import time

from app import aggregator, catalog, mapper
from app.sources.vision_azure import VisionAzure
from app.sources.vision_llm import VisionLLM
from app.sources.vision_reciclapi import VisionReciclAPI

LOG = logging.getLogger("wasteai.health")
TIMEOUT = 6.0
ALT_SHOWN = 2


class AllSourcesFailed(Exception):
    pass


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _pairs(top) -> list[tuple[str, float]]:
    out = []
    for t in top or []:
        if isinstance(t, tuple | list):
            out.append((str(t[0]), float(t[1])))
        else:
            out.append((str(_get(t, "label", "")), float(_get(t, "score", 0.0))))
    return out


async def _call(name: str, src, data: bytes):
    fn = next((getattr(src, m) for m in ("classify", "predict", "run") if hasattr(src, m)), None)
    try:
        res = fn(data)
        if inspect.isawaitable(res):
            res = await asyncio.wait_for(res, TIMEOUT)
        pairs = _pairs(_get(res, "top", []))
        return name, bool(_get(res, "ok", False)), pairs
    except Exception:  # a failing source is skipped, never fatal
        return name, False, []


async def _timed(name: str, src, data: bytes, timings: dict):
    """Run one source call and record its duration (monotonic clock, ms)."""
    t = time.perf_counter()
    res = await _call(name, src, data)
    timings[name] = max(0, int((time.perf_counter() - t) * 1000))
    return res


def _source_items(results, timings: dict) -> list[dict]:
    return [{"name": n, "ok": ok,
             "top": [{"label": lb, "score": round(sc, 4)} for lb, sc in p[:3]],
             "elapsed_ms": timings.get(n)}
            for n, ok, p in results]


def _hazard_warning(cats: dict) -> list[str]:
    """Generic hazard note, taken from the content files (never hard-coded here)."""
    ref = cats.get("hazardous_chemical", {}).get("warnings", [])
    return ref[-1:]


class Orchestrator:
    def __init__(self, local, azure: VisionAzure, recicl: VisionReciclAPI, llm=None) -> None:
        self.local, self.azure, self.recicl, self.llm = local, azure, recicl, llm
        self.sources = []
        if local is not None:
            self.sources.append(("local_onnx", local))
        if azure.enabled:
            self.sources.append(("azure", azure))
        if recicl.enabled:
            self.sources.append(("reciclapi", recicl))

    def local_status(self) -> str:
        if self.local is None:
            return "down"
        return getattr(self.local, "health", {}).get("status", "up")

    async def startup_selftests(self) -> dict:
        """Run at startup: real local inference + cheap Azure check; logs source_status."""
        if self.local is not None and hasattr(self.local, "selftest"):
            await asyncio.to_thread(self.local.selftest)
        LOG.info("source_status", extra={"event": "source_status", "source_status": self.statuses()})
        return self.statuses()

    async def deep(self) -> dict:
        """Admin view: re-run the local self-test, hourly real Azure call, quota use."""
        local = {"status": "down", "reason": "not_loaded"}
        if self.local is not None and hasattr(self.local, "selftest"):
            local = await asyncio.to_thread(self.local.selftest)
        azure = await self.azure.deep_check()
        try:
            from app import quota
            azure["quota_used"], azure["quota_limit"] = quota.used(), quota.LIMIT
        except Exception:
            azure["quota_used"] = None
        return {"local_onnx": local, "azure": azure}

    def statuses(self) -> dict:
        return {
            "local_onnx": self.local_status(),
            "azure": self.azure.status(),
            "reciclapi": "up" if self.recicl.enabled else "disabled",
            "llm": self.llm.status() if self.llm is not None else "disabled",
        }

    def llm_active(self) -> bool:
        return self.llm is not None and bool(self.llm.enabled)

    async def run(self, data, lang: str, request_id: str, allow_cloud_llm: bool = False) -> dict:
        t0 = time.perf_counter()
        timings: dict[str, int] = {}
        results = await asyncio.gather(*[_timed(n, s, data, timings) for n, s in self.sources])
        if not any(ok for _, ok, _ in results):
            raise AllSourcesFailed
        answered = [n for n, ok, _ in results if ok]
        if len(self.sources) > 1 and len(answered) == 1:
            LOG.warning("degraded", extra={
                "event": "degraded", "request_id": request_id,
                "source_status": {n: ok for n, ok, _ in results}})
        cats = catalog.by_id(lang)
        usable = {}
        for name, ok, pairs in results:
            scores = mapper.map_labels(pairs) if ok else {}
            if scores:
                usable[name] = scores
        first = aggregator.decide(usable) if usable else None
        # Tiebreaker: flag on + per-photo consent + unclear first pass; never after a hazard.
        if (allow_cloud_llm and self.llm_active() and not (first and first.hazard)
                and (first is None or first.status != "ok" or first.agreement == "none")):
            name, ok, pairs = await _timed("llm", self.llm, data, timings)
            results.append((name, ok, pairs))
            scores = mapper.map_labels(pairs) if ok else {}
            if scores:
                usable[name] = scores
        if not usable:
            return {
                "request_id": request_id,
                "status": "uncertain",
                "category": None,
                "alternatives": [],
                "agreement": "none",
                "hazard": False,
                "guidance": None,
                "sources": _source_items(results, timings),
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            }
        d = aggregator.decide(usable)
        is_ok = d.status == "ok"

        def brief(cid: str, score: float) -> dict:
            return {"id": cid, "name": cats.get(cid, {}).get("name", cid),
                    "confidence": round(score, 2)}

        reason: list[str] = []
        why_id = d.category_id if is_ok else d.hazard_id
        if why_id:
            targets = [why_id]
            if d.fallback:  # group default: explain through the two ranked categories
                targets = [c for c, _ in d.alternatives]
            for name, _ok, pairs in results:
                for t in targets:
                    reason += [f"{name}:{lb}>{t}" for lb in mapper.matching_labels(pairs, t)]
        if d.fallback:
            reason.append("group_fallback")
        guide_id = d.category_id if is_ok else d.hazard_id
        guidance = None
        if guide_id:
            g = cats.get(guide_id, {})
            warnings = list(g.get("warnings", []))
            if d.hazard_id and not warnings:
                warnings = _hazard_warning(cats)
            guidance = {"bin": g.get("bin", "special"), "summary": g.get("summary", ""),
                        "steps": g.get("steps", []), "warnings": warnings}
        category = None
        if is_ok:
            category = {"id": d.category_id, "name": cats.get(d.category_id, {}).get("name", d.category_id),
                        "group": cats.get(d.category_id, {}).get("group", ""),
                        "confidence": round(d.confidence, 2)}
        return {
            "request_id": request_id,
            "status": "ok" if is_ok else "uncertain",
            "category": category,
            "alternatives": [brief(c, v) for c, v in d.alternatives[:ALT_SHOWN]],
            "agreement": d.agreement,
            "hazard": d.hazard,
            "guidance": guidance,
            "reason": reason,
            "sources": _source_items(results, timings),
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        }


def build_orchestrator() -> Orchestrator:
    local = None
    try:
        from app.sources.vision_local import VisionLocal

        local = VisionLocal.from_env()
        try:
            local.load()
        except Exception as exc:
            local.mark_down("model_file_missing" if "not found" in str(exc)
                            else f"load_error:{type(exc).__name__}")
    except Exception:
        local = None
    return Orchestrator(local, VisionAzure.from_env(), VisionReciclAPI.from_env(),
                        VisionLLM.from_env())


def get_orchestrator(app) -> Orchestrator:
    if getattr(app.state, "orchestrator", None) is None:
        app.state.orchestrator = build_orchestrator()
    return app.state.orchestrator
