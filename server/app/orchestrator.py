# File: server/app/orchestrator.py
import asyncio
import inspect
import time

from app import aggregator, catalog, mapper
from app.sources.vision_azure import VisionAzure
from app.sources.vision_reciclapi import VisionReciclAPI

TIMEOUT = 6.0
ALT_SHOWN = 2


class AllSourcesFailed(Exception):
    pass


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _pairs(top) -> list[tuple[str, float]]:
    out = []
    for t in top or []:
        if isinstance(t, (tuple, list)):
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
        return name, bool(_get(res, "ok", False)) and bool(pairs), pairs
    except Exception:  # a failing source is skipped, never fatal
        return name, False, []


def _hazard_warning(cats: dict) -> list[str]:
    """Generic hazard note, taken from the content files (never hard-coded here)."""
    ref = cats.get("hazardous_chemical", {}).get("warnings", [])
    return ref[-1:]


class Orchestrator:
    def __init__(self, local, azure: VisionAzure, recicl: VisionReciclAPI) -> None:
        self.local, self.azure, self.recicl = local, azure, recicl
        self.sources = []
        if local is not None:
            self.sources.append(("local_onnx", local))
        if azure.enabled:
            self.sources.append(("azure", azure))
        if recicl.enabled:
            self.sources.append(("reciclapi", recicl))

    def statuses(self) -> dict:
        return {
            "local_onnx": "up" if self.local is not None else "down",
            "azure": self.azure.status(),
            "reciclapi": "up" if self.recicl.enabled else "disabled",
        }

    async def run(self, data: bytes, lang: str, request_id: str) -> dict:
        t0 = time.perf_counter()
        results = await asyncio.gather(*[_call(n, s, data) for n, s in self.sources])
        if not any(ok for _, ok, _ in results):
            raise AllSourcesFailed
        cats = catalog.by_id(lang)
        usable = {}
        for name, ok, pairs in results:
            scores = mapper.map_labels(pairs) if ok else {}
            if scores:
                usable[name] = scores
        if not usable:
            raise AllSourcesFailed
        d = aggregator.decide(usable)
        is_ok = d.status == "ok"

        def brief(cid: str, score: float) -> dict:
            return {"id": cid, "name": cats.get(cid, {}).get("name", cid),
                    "confidence": round(score, 2)}

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
            "sources": [
                {"name": n, "ok": ok, "top": [{"label": lb, "score": round(s, 4)} for lb, s in p[:3]]}
                for n, ok, p in results
            ],
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        }


def build_orchestrator() -> Orchestrator:
    local = None
    try:
        from app.sources.vision_local import VisionLocal

        local = VisionLocal.from_env()
        local.load()
    except Exception:
        local = None
    return Orchestrator(local, VisionAzure.from_env(), VisionReciclAPI.from_env())


def get_orchestrator(app) -> Orchestrator:
    if getattr(app.state, "orchestrator", None) is None:
        app.state.orchestrator = build_orchestrator()
    return app.state.orchestrator
