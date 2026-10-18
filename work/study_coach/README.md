# FlyRank Study Coach — FL-09 build

**What it is:** a terminal agent that quizzes me from my own FlyRank internship notes. It picks my weakest-scoring topic, asks five questions one at a time, grades each answer 0–2 against the exact section it came from (with a citation line), and appends every answer to a ledger so weak topics come back until they stick.

**Who it's for:** an intern (me, Week 1–8) drowning in docs — data dictionary, lane guide, skills — who needs retrieval practice more than re-reading. Also anyone learning with a folder of markdown notes: point the whitelist at your own files and it works the same.

Design spec: `submission/week 5/design_your_personal_agent_FL-06.txt`.

## Setup (a stranger could follow this)

Nothing to install — Python 3.10+, standard library only.

```bash
git clone https://github.com/Abdullah-9862873/FlyRank-Internship.git
cd FlyRank-Internship

# offline first (no key, deterministic local grader):
python work/study_coach/coach.py --mock --questions 5

# live (free-tier keys, ~2 minutes total):
#   1. Gemini key: https://aistudio.google.com/apikey  (or Groq: https://console.groq.com)
#   2. put in .env at repo root (never in a notebook cell):
#        GEMINI_API_KEY=your-key
#        GROQ_API_KEY=your-key        # optional but recommended: fallback provider
#   3. run:
python work/study_coach/coach.py --questions 5
```

## Usage examples

```bash
python work/study_coach/coach.py --list-topics          # 83 topics across the docs
python work/study_coach/coach.py --topic "docs/data-dictionary.md#Identifiers"
python work/study_coach/coach.py --mock --questions 2   # quick deterministic session
python work/study_coach/evals.py                        # full eval suite → work/outputs/coach_evals.json
```

A session looks like this (mock mode, abbreviated):

```
Topic: docs/data-dictionary.md#Identifiers
Q1: What do the content_id and client_id columns uniquely identify?
You: content_id is a page, client_id is the site owner.
Grade: 1/2 — correct that content_id is the page; add that client_id groups pages into one site's portfolio.
Q2: ...
```

## Architecture sketch

```
            ┌──────────────┐
  .env ───► │   llm.py     │  Gemini → Groq → offline mock (circuit breaker 300s)
            └──────┬───────┘
                   │ graded / asked
            ┌──────▼───────┐     whitelist read      ┌──────────────────────┐
  you ────► │   coach.py   │ ◄────────────────────── │ docs/*.md, skills/** │
  (CLI)     │ session loop │      refuses data/      └──────────────────────┘
            └──────┬───────┘
                   │ append-only receipts
            ┌──────▼───────────────────────┐
            │ work/outputs/coach_log.json  │  + coach_events.jsonl
            └──────────────────────────────┘
  evals.py  ──► runs E1–E5 against the same loop, writes coach_evals.json
```

## v2 eval results (live run, 2026-10-17)

`python work/study_coach/evals.py` → all five PASS with a live model as grader:

| Eval | What it proves | Status |
|---|---|---|
| E1 happy path session | 3 questions asked, graded by live model, ledgered | PASS |
| E2 hallucination trap | invented metric scored 0 with "not in my notes" | PASS |
| E3 prompt-injection boundary | injection logged, model stayed on task, no prompt leak | PASS |
| E4 ledger integrity | 2 sessions × 5 questions = 10 valid entries, schema intact | PASS |
| E5 rate-limit fallback | Gemini 429 simulated → wait/retry → fallback completed the run | PASS |

Raw receipts: `work/outputs/coach_evals.json`, `work/outputs/coach_log.json`, `work/outputs/coach_events.jsonl`.

## Guardrails (hard rules, enforced in code)

- Reads only `docs/data-dictionary.md`, `docs/ml-intern-dataset-and-lane-guide.md`, and `skills/**/SKILL.md` — anything under `data/` is refused.
- Writes only `work/outputs/coach_log.json` + `coach_events.jsonl`.
- Never runs the pipeline, never invents FlyRank facts ("not in my notes" path).
- API keys from env/`.env` only — `.env` is gitignored.

## Limitations (the honest list)

1. **Whitelist-only reading.** It cannot answer from the wider web or from files outside three allowed paths. Deliberate (privacy > coverage), but it means "what's the capital of Pakistan" is out of scope by design.
2. **No weekly summary / spaced-repetition scheduler yet.** The FL-06 spec's weekly rollup was cut for MVP; "weak topics come back" currently means weakest-topic-first picking, not a real SRS schedule.
3. **Provider quota fragility.** Gemini free tier rate-limits hard; the Groq fallback keeps sessions alive, but two free-tier providers are still two free tiers. Shown live in eval E5.
4. **Grading ceiling.** Offline mock grading is deterministic but shallower than the live model; evals honestly mark offline runs `PASS-OFFLINE`/`SKIP-NEEDS-KEY` rather than faking a live pass.
5. **English-only, terminal-only.** No i18n, no web UI — it's a CLI study tool, not a product.

## Where AI did the work (transparency line)

This agent was built with an AI coding assistant doing the drafting — the four modules (`coach.py`, `tools.py`, `llm.py`, `evals.py`) and the eval harness were AI-written under my direction from the FL-06 spec. What I verified myself, with receipts: I ran every eval before and after each change, hand-ran live and mock sessions, caught a silent grader-scoring bug in review (build_log Session 3 — evals were green while every offline grade was silently 0), and re-ran the full suite twice for determinism. The guardrails (data/ refusal, append-only writes, key handling) were my design decisions, implemented by the assistant and tested by me. Framework honesty map: https://general-ai-fluency.netlify.app/study-4d
