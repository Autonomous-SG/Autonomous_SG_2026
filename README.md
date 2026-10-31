# Vector — multi-agent disruption negotiation (Autonomous SG 2026, Airbus Challenge #2)

When a runway closes or weather hits a hub, **ATC, the airline and ground ops** each hold information the others can't see — fuel, gate occupancy, crew rosters, runway reopening times — and today they reconcile it by phone. Vector lets three independent Claude agents, one per organisation, negotiate a revised **landing time, gate and turnaround** for a disrupted flight in **at most 3 turns**, while **code — not the LLM — enforces every safety rule**. A duty manager approves or rejects the result.

**User:** the airline Operations Control duty manager at a hub, coordinating with tower and ramp control during a disruption.

## How it works

```
flights.csv row (real DOT 2015 disruption) ──► world builder ──► public data + 3 private slices
                                                                    │
  solver (public data only) ──► options ──► 3 Claude agents in parallel (each sees ONLY its own private notes)
                                              │  ACCEPT + score 0–10, or VETO citing a hard rule in its own domain,
                                              │  plus at most one counter-proposal
                                              ▼
  rule checker (referee) verifies every veto and counter ──► confirmed vetoes become shared constraints
                                              ▼
  converge in ≤ 3 turns ──► final safety gate ──► decision rule ──► CONSENSUS / FALLBACK / NO_FEASIBLE
                                                                         ▼
                                                        duty manager Approve / Reject (UI)
```

| Done by the LLM agents | Done by deterministic code |
|---|---|
| Read messy private notes (ACARS, ramp, tower) | Wake separation, fuel reserve, gate conflicts, crew limits, turnaround, equipment |
| Score options for their organisation, explain why | Generate options (grid search), verify vetoes, check counters |
| Propose counter-plans (e.g. expedited turnaround) | Combine votes (best worst-case score), turn limit, fallback, final safety gate |

**Why multiple agents:** the three organisations don't share raw data. A solver that only sees public data picks plans that fail in reality; agents reveal just enough (as verified vetoes) to fix that.

## Results (live, `backend/eval/summary.md`)

40 live negotiations on random real `flights.csv` rows (24 scenarios × 3 event types, plus 16 red-team runs).

| | Plans that fail a hard rule in reality | Mean arrival delay | Mean next-leg delay | Connecting pax missed |
|---|---|---|---|---|
| Solver only (public data) | **83%** (20/24) | 48.7 min | 43.4 min | 35 |
| **Negotiated (Vector)** | **0%** | **25.7 min** | **25.5 min** | **19** |
| Oracle (solver given everyone's private data) | 0% | 25.6 min | 30.5 min | 19 |
| Naive single prompt (one Claude call plays all 3 roles, sees all data, told every rule) | **33%** (8/24) | 30.4 min | 27.0 min | 35 |
| What happened in 2015 (real weather) | — | 83.5 min | 57.0 min | — |

- **0 unsafe recommendations** in 40 runs. Consensus 83%, fallback 4%, escalated (no feasible plan) 12%.
- **Why not one prompt?** The challenge says not to combine the three roles. We measured it anyway: a single call with all the data still broke a hard rule in a third of the same scenarios (landing on a closed runway ×5, busy gate ×3). Splitting roles and verifying in code is what gets it to zero.
- 79% converge in ≤ 2 turns; ~11 s and ~$0.07 per negotiation; 0 invalid LLM outputs.
- **Red team:** prompt injection, lying agent, agent timeout, no-feasible scenario — 0 unsafe outcomes; every false veto rejected.
- **Where it fails:** agents accepted 17 options that break a hard rule (mostly small airports with 1 runway and 2 spare gates); the final safety gate removed all of them. The checker also rejected 15 false vetoes. 2015 delays come from real weather, not our injected events, so that row is indicative only.

## Stated assumptions

Limits come from the organisers' `data/challenge2_operational_constraints.xlsx` (synthetic planning values) via `backend/negotiation/constraints.py`.
1. Flights, delays, tail numbers and next legs are real (DOT 2015). Events, queue timings, gate occupancy, crews, equipment, fuel and connections are synthetic, seeded per scenario, and labelled in the UI.
2. Wake separation (NM table) converted to minutes at 140 kt final-approach speed; Heavy/Large/Small = HEAVY/MEDIUM/LIGHT; Super not modelled.
3. Turnaround: expedited = workbook minimum, standard = minimum + 10 min.
4. Spare fuel defaults to 45 min of holding; scenarios may reduce it and say so.
5. Ground overtime allowed at 1.5× cost unless a scenario states the crew's overtime cap is reached.
6. Gate-change notice (20 min) measured from now to in-gate time. Flight-crew 13 h duty not modelled.

## Run it

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.sample .env        # add ANTHROPIC_API_KEY
.venv/bin/uvicorn main:app --port 8000
```

```bash
cd frontend/autonomous_hackathon && npm install && npm run dev    # http://localhost:5173 → "Live backend"
```

Put `flights.csv` from the Challenge #2 folder in `data/`. Other entry points (from `backend/`):
- `.venv/bin/python -m scripts.run_once --row 20919` — one negotiation in the terminal
- `.venv/bin/python -m scripts.check_deps --real` — offline integration check, no API cost
- `.venv/bin/python -m scripts.run_eval --rows 24 --attack-rows 4` — live batch eval + red-team scorecard
- `.venv/bin/python -m scripts.run_naive` — naive single-prompt baseline on the same scenarios
- `.venv/bin/pytest tests/` — world builder tests

## Repo map

| Path | What |
|---|---|
| `backend/negotiation/world.py`, `data.py` | Scenario builder from `flights.csv` + workbook limits |
| `backend/negotiation/rules.py`, `solver.py`, `decision.py`, `baselines.py` | Rule checker, option solver, decision rule, evaluation baselines |
| `backend/negotiation/agents/*.md`, `agent_runner.py`, `orchestrator.py` | Agent prompts, Claude calls with guardrails, 3-turn protocol |
| `backend/negotiation/schemas.py` | Shared data contract |
| `frontend/autonomous_hackathon/` | Duty-manager UI (React + Vite) |
| `PLAN.md` | Full design, protocol, guardrails and team split |
