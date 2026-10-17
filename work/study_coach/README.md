# FlyRank Study Coach — FL-07 build

A scripted agent that quizzes me from my own FlyRank notes, grades each answer
against the section it came from, and logs every answer so weak topics come back
until they stick. Design spec: `submission/week 5/design_your_personal_agent_FL-06.txt`.

## Run it

Nothing to install — Python 3.10+ standard library only.

```bash
# offline (no key, deterministic local grader)
python work/study_coach/coach.py --mock --questions 5

# live (Gemini free tier, Groq as automatic fallback)
# 1. get a Gemini key: https://aistudio.google.com/apikey  (free, ~1 min)
#    and/or a Groq key: https://console.groq.com  (free, ~1 min)
# 2. add the lines to the .env file at the repo root — never a code cell:
#      GEMINI_API_KEY=your-key-here
#      GROQ_API_KEY=your-key-here
# 3. run:
python work/study_coach/coach.py --questions 5

# pick a topic yourself (ids from the list)
python work/study_coach/coach.py --list-topics
python work/study_coach/coach.py --topic "docs/data-dictionary.md#Identifiers"
```

Optional second provider for the rate-limit fallback: `GROQ_API_KEY=` in `.env`.

## What it does, in order

1. Picks a topic: my weakest-scoring topic so far, else the first one in the notes.
2. Reads that section from the repo (whitelist only — `data/` is refused by design).
3. Asks 5 questions, one at a time; I answer in the terminal.
4. Grades each 0–2 against the section text, with a citation line back into the notes.
5. Appends every answer to `work/outputs/coach_log.json` (the receipts).

## Files

| File | Job |
|---|---|
| `coach.py` | CLI session loop (entry point) |
| `tools.py` | the agent's tools + read whitelist guardrail |
| `llm.py` | Gemini → Groq → offline fallback chain, event log |
| `evals.py` | pre-build eval cases E1–E5 from the FL-06 spec |
| `build_log.md` | what broke, what changed, what deviated |

## Eval harness (E1–E5, written before building)

```bash
python work/study_coach/evals.py
```

Writes `work/outputs/coach_evals.json`. With no key it runs offline and marks
the two content evals honestly (`PASS-OFFLINE` / `SKIP-NEEDS-KEY`) instead of
faking a pass; with `GEMINI_API_KEY` or `GROQ_API_KEY` set, E1–E3 run live
and assert the grader was a real model, never the mock.

## Guardrails (hard rules, enforced in code)

- Reads only `docs/data-dictionary.md`, `docs/ml-intern-dataset-and-lane-guide.md`,
  and `skills/**/SKILL.md` — anything under `data/` is refused.
- Writes only `work/outputs/coach_log.json` + `coach_events.jsonl`.
- Never runs the pipeline, never invents FlyRank facts ("not in my notes" path).
- API keys from env/`.env` only — `.env` is gitignored, keys never enter a cell.
