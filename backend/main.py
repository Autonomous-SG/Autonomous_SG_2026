from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from negotiation.agent_runner import model_name  # noqa: E402
from negotiation.orchestrator import Log, load_deps, negotiate  # noqa: E402
from negotiation.schemas import (  # noqa: E402
    HumanDecisionRequest, NegotiateRequest, NegotiationResult, ScenarioSummary,
)

app = FastAPI(title="ATC / Pilot / Ground Negotiation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

DEPS = load_deps()
RESULTS: dict[str, NegotiationResult] = {}


@app.get("/api/health")
def health():
    return {"status": "ok", "model": model_name(), "deps": DEPS.sources}


@app.get("/api/scenarios", response_model=list[ScenarioSummary])
def scenarios(airport: str | None = None, date: str | None = None, limit: int = 50):
    return DEPS.list_scenarios(airport, date, limit)


@app.post("/api/negotiate", response_model=NegotiationResult)
async def run_negotiation(req: NegotiateRequest):
    try:
        result = await negotiate(req, DEPS)
    except (ValueError, KeyError, IndexError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    RESULTS[result.scenario_id] = result
    return result


@app.post("/api/decision")
def human_decision(req: HumanDecisionRequest):
    result = RESULTS.get(req.scenario_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown scenario_id; run /api/negotiate first.")
    log = Log()
    log.entries = result.log
    log.add(result.decision.rounds_used, "HUMAN", "HUMAN_DECISION",
            f"Duty manager {'APPROVED' if req.approve else 'REJECTED'} the recommendation"
            + (f": {req.note}" if req.note else ""))
    return {"ok": True, "approved": req.approve}
