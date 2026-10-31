# Vector — multi-agent disruption negotiation

**Team Vector** · Autonomous SG 2026 · Airbus track, Challenge #2 (“How might AI help air traffic controllers, pilots and ground operations staff make faster and better decisions?”)

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

**Option letters:** the solver offers A–C in turn 1 and more in turn 2; a counter-proposal from an agent takes the next free letter and is voted on in the following turn. If the deterministic fallback has to decide, its plan also takes the next letter.

## How do we know a plan is correct?

Historical data records what happened, not what the best plan would have been, so there is no ground-truth answer to copy. Every plan is checked three ways instead:
1. **Legal** — a deterministic rule checker tests every hard rule against the scenario's full data and shows pass/fail evidence per rule (UI: “Checker evidence”). A final safety gate re-checks the recommendation even if all agents accepted it.
2. **Optimal** — an oracle solver that sees everyone's private data and tries every slot × runway × gate × turnaround gives the best possible plan under the same cost rules; we compare against it (UI: “04 / Compare”).
3. **Better than reality** — the real 2015 outcome of the same flight shows the scale of the problem (indicative only: it was caused by real weather, not our injected event).

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
cd frontend/autonomous_hackathon && npm install && npm run dev    # http://localhost:5173 (add -- --port 5180 if 5173 is taken)
```

Put `flights.csv` from the Challenge #2 folder in `data/` (not committed; 38.6 MB). The constraints workbook is already in `data/`.

### Try it in 2 minutes
1. Open the UI; it loads real flights from the backend (first load ~3 s).
2. Destination airport **ATL**, date **12/01/2015**, flight **DL912 · ORD → ATL** (the reference case), disruption **Runway closure** → **Run negotiation** (10–20 s, ~$0.10).
3. Read the timeline (votes, vetoes, checker evidence, shared constraints), the recommendation and the comparison; click **Approve** or **Reject**. A rejected plan is never offered again for that flight and disruption (remembered until the backend restarts); rerun to get the next-best plan.
4. Try any of the 320 destination airports, the three disruption types, and the test conditions: prompt injection, contradictory agent notes, agent timeout, no feasible plan.
5. Offline backup: **Import saved result** → `backend/fixtures/negotiation_example.json` (a real recorded run; attack runs in `backend/fixtures/attack_*.json`).

### Other entry points (from `backend/`)
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
| `backend/negotiation/constraints.py` | Organiser workbook limits (airports, wake table, fuel and crew rules) |
| `backend/negotiation/naive.py` | Evaluation-only single-prompt baseline |
| `backend/negotiation/schemas.py` | Shared data contract |
| `backend/scripts/`, `backend/eval/`, `backend/fixtures/` | Run/eval scripts, evaluation results, recorded runs |
| `frontend/autonomous_hackathon/` | Duty-manager UI (React + Vite) |
| `PLAN.md` | Full design, protocol, guardrails and team split |

## Limits and next steps

Private operational data is synthetic; one disrupted flight at a time; three disruption types (the ones the challenge names). Next: multi-flight disruption waves where several flights compete for slots, and live airline / ATC data feeds.

## Team

| Role | Who |
|---|---|
| World builder (scenarios from `flights.csv` + workbook) | Jasmitha |
| Rules, solver, decision rule, baselines | Deepa |
| Agents, orchestrator, API, evaluation | [name] |
| Duty-manager UI | Sania |
