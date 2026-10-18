# FL-09 demo run-sheet — 3–5 minutes, live, no slides

Record the terminal (OBS screen capture or `asciinema`), narrate out loud. One continuous run — mistakes are fine, they prove it's live.

## Beat 1 — the question (0:00–0:30)
"I'm interning in ML at FlyRank and drowning in docs. This is an agent that quizzes me from my own notes instead of letting me re-read passively. Watch a real session."

## Beat 2 — mock run first, fast (0:30–1:15)
```bash
python work/study_coach/coach.py --mock --questions 2
```
Narrate: "Deterministic offline mode — no API key, same grades every time. This is how I sanity-check before spending free-tier quota."

## Beat 3 — live run (1:15–3:00)
```bash
python work/study_coach/coach.py --questions 3
```
Answer a question badly on purpose once. Narrate what's happening: "It read only the whitelisted section for this topic — it can't read my data folder, that's refused in code. Grading is a live model now; here's the citation back into my notes."

## Beat 4 — one design decision on camera (3:00–3:40)
Point at the guardrail in `tools.py`. **Design decision to explain:** "The agent only reads three allowed files and refuses anything under `data/`. Privacy over coverage — I'd rather it say 'not in my notes' than leak client data into a prompt."

## Beat 5 — one limitation on camera, with proof (3:40–4:30)
```bash
python work/study_coach/evals.py     # or narrate E5 from the last run
```
**Limitation to explain:** "Gemini's free tier rate-limits constantly — a real 429 killed my first recording session. The agent waits, retries, and falls back to Groq (eval E5 proves the path), but two free tiers are still fragile. And the weekly-summary feature from my spec? Cut for the MVP — it doesn't exist yet. The receipts say PASS, not perfect."

## Beat 6 — close (4:30–5:00)
"Eval receipts are in work/outputs/coach_evals.json — all five passed live. README has the stranger-setup. That's the honest state of it."

## Checklist before recording
- [ ] `.env` has GEMINI_API_KEY and GROQ_API_KEY
- [ ] Terminal font zoomed ≥16px, dark theme
- [ ] Close unrelated tabs (no keys visible on screen — never show .env)
- [ ] One continuous take; upload unlisted; paste the link in the showcase thread + portal
