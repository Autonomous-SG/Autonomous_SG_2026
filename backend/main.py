from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from negotiation.agent_runner import model_name  # noqa: E402
from negotiation.orchestrator import Log, load_deps, negotiate  # noqa: E402
from negotiation.schemas import (  # noqa: E402
    HumanDecisionRequest, NegotiateRequest, NegotiationResult, Option, ScenarioSummary,
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
# Plans the duty manager rejected, per "row_id:event". In memory: cleared when the backend restarts.
REJECTED: dict[str, list[Option]] = {}


def _scenario_key(row_id: int, event: str) -> str:
    return f"{row_id}:{event}"


@app.get("/api/health")
def health():
    return {"status": "ok", "model": model_name(), "deps": DEPS.sources}


@app.get("/api/scenarios", response_model=list[ScenarioSummary])
def scenarios(airport: str | None = None, date: str | None = None, limit: int = 50):
    return DEPS.list_scenarios(airport, date, limit)


@app.post("/api/negotiate", response_model=NegotiationResult)
async def run_negotiation(req: NegotiateRequest):
    try:
        result = await negotiate(req, DEPS, rejected=REJECTED.get(_scenario_key(req.row_id, req.event), []))
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
            + (f": {req.note}" if req.note else "")
            + (" — this plan will not be offered again for this flight and disruption"
               if not req.approve and result.decision.option else ""))
    if not req.approve and result.decision.option:
        pub = result.world.public
        plans = REJECTED.setdefault(_scenario_key(pub.flight.row_id, pub.event.type), [])
        o = result.decision.option
        if all((p.landing_time, p.runway, p.gate, p.turnaround) != (o.landing_time, o.runway, o.gate, o.turnaround)
               for p in plans):
            plans.append(o)
    return {"ok": True, "approved": req.approve}
