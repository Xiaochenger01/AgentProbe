from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from . import __version__
from .regression import load_report
from .report import aggregate, to_markdown


def create_app(runs_dir: str = "runs") -> FastAPI:
    app = FastAPI(title="AgentProbe", version=__version__)
    rd = Path(runs_dir)

    @app.get("/")
    def index():
        return {
            "name": "AgentProbe",
            "version": __version__,
            "endpoints": ["/runs", "/runs/{run_id}", "/runs/{run_id}/report",
                          "/dashboard", "/dashboard/{run_id}", "/dashboard/compare"],
        }

    @app.get("/runs")
    def list_runs():
        out = []
        for p in sorted(rd.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                rep = load_report(p)
            except Exception:  # noqa: BLE001
                continue
            out.append({"run_id": rep.run_id, "agent": rep.agent, "file": p.name, **aggregate(rep)})
        return out

    def _find(run_id: str) -> Path:
        for p in rd.glob("*.json"):
            if p.stem == run_id or p.stem.startswith(run_id):
                return p
        raise HTTPException(404, f"run {run_id} not found")

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        return JSONResponse(content=load_report(_find(run_id)).model_dump())

    @app.get("/runs/{run_id}/report", response_class=PlainTextResponse)
    def get_report(run_id: str):
        return to_markdown(load_report(_find(run_id)))

    # ---- Dashboard HTML routes ----
    from .dashboard import register_dashboard_routes
    register_dashboard_routes(app, runs_dir)

    return app
