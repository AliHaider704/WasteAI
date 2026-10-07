# File: server/app/orchestrator.py
import asyncio
import inspect
import time

from app import catalog, mapper
from app.sources.vision_azure import VisionAzure
from app.sources.vision_reciclapi import VisionReciclAPI

TIMEOUT = 6.0
WEIGHTS = {"local_onnx": 0.6, "azure": 0.4, "reciclapi": 0.3}
OK_MIN, SINGLE_MIN, HAZARD_MIN = 0.65, 0.80, 0.35
FALLBACK_WARN = {
    "en": "Check with your local authorities for correct disposal.",
    "ar": "تحقق من الجهات المحلية لمعرفة طريقة التخلص الصحيحة.",
}


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


def _agreement(usable: dict, cats: dict) -> str:
    if len(usable) < 2:
        return "single_source"
    tops = [max(s, key=s.get) for s in usable.values()]
    if len(set(tops)) == 1:
        return "full"
    groups = {cats.get(t, {}).get("group") for t in tops}
    return "partial" if len(groups) == 1 else "none"


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
        total_w = sum(WEIGHTS[n] for n in usable)
        comb: dict[str, float] = {}
        for n, s in usable.items():
            for c, v in s.items():
                comb[c] = comb.get(c, 0.0) + WEIGHTS[n] / total_w * v
        ranked = sorted(comb.items(), key=lambda kv: -kv[1])
        agreement = _agreement(usable, cats) if usable else "none"
        top_id, top_score = ranked[0] if ranked else (None, 0.0)
        is_ok = top_id is not None and top_score >= OK_MIN and (
            agreement in ("full", "partial")
            or (agreement == "single_source" and top_score >= SINGLE_MIN)
        )

        def brief(cid: str, score: float) -> dict:
            return {"id": cid, "name": cats.get(cid, {}).get("name", cid),
                    "confidence": round(score, 2)}

        hazard_id = next((c for c, v in ranked[:2] if catalog.is_hazard(c) and v >= HAZARD_MIN), None)
        guide_id = top_id if is_ok else hazard_id
        guidance = None
        if guide_id:
            g = cats.get(guide_id, {})
            warnings = list(g.get("warnings", []))
            if hazard_id and not warnings:
                warnings = [FALLBACK_WARN[lang]]
            guidance = {"bin": g.get("bin", "special"), "summary": g.get("summary", ""),
                        "steps": g.get("steps", []), "warnings": warnings}
        category = None
        if is_ok:
            category = {**brief(top_id, top_score), "group": cats.get(top_id, {}).get("group", "")}
            category = {"id": category["id"], "name": category["name"],
                        "group": category["group"], "confidence": category["confidence"]}
        return {
            "request_id": request_id,
            "status": "ok" if is_ok else "uncertain",
            "category": category,
            "alternatives": [brief(c, v) for c, v in (ranked[1:3] if is_ok else ranked[:2])],
            "agreement": agreement,
            "hazard": hazard_id is not None,
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
