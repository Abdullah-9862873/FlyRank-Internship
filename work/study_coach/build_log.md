# FL-07 Build Log — FlyRank Study Coach

Scope: MVP of the FL-06 spec. Narrowest version of the core job first: one
session, one topic, questions → answers → graded → ledgered, with live file
tools. No weekly summary feature yet (cut deliberately, see Deviations).

---

## Session 1 — scaffold from the spec

Wrote the four pieces straight from the FL-06 design: `llm.py` (provider
fallback), `tools.py` (4 tools + whitelist), `coach.py` (session loop),
`evals.py` (E1–E5 defined first, then built against). Stdlib only — no new
requirements, because the repo's `requirements.txt` is the reference pipeline's.

**Broke immediately:** first `evals.py` run crashed on a traceback in E3 —
`heading not found`. I had hardcoded the full heading text of a
data-dictionary section, and it did not match the file byte-for-byte
(em dash vs plain hyphen in the heading).

**Changed:** no more hardcoded heading strings anywhere. Added
`find_topic(fragment)` — evals now discover topic ids by substring against
`list_topics()`. The guardrail refusing an unknown heading was correct
behaviour; the test input was the bug.

---

## Session 2 — topics list came back nearly empty

`list_topics()` collected only `###` level-3 headings. The data dictionary is
written with `##` sections, so **the primary study document contributed zero
topics** (9 topics total, all from the lane guide). Caught by printing
`len(list_topics())` before building the topic picker on top of it.

**Changed:** headings levels 2–3 both collected → 83 topics across the data
dictionary, lane guide, and skills. Added `find_topic()` in the same pass.

---

## Session 3 — a real run caught a silent scoring bug

Eval counts were green, so I ran an actual session by hand (`--mock --questions
2`). Output showed `score 0/2` with an empty note on a full-sentence answer.
Reading `call_mock`: the grade/question branch keyed on
`"GRADE THIS ANSWER" in system_prompt` — but that marker is appended to the
**user** prompt, so grading always fell through to the question branch, the
`score` key was missing, and `_coerce_score(None)` quietly returned 0. Every
offline grade would have been 0 while evals still "passed" (they counted
entries, not scores).

**Changed:** branch on `user_prompt`, split the answer block explicitly, added
a deterministic question template that quotes the actual heading. Re-ran a
hand session: `score 1/2` with notes printed. Re-ran full evals twice —
identical output both times (deterministic).

---

## Session 4 — eval honesty pass

Ran `evals.py` end to end with no API key present:

```
E1  PASS-OFFLINE   3 questions asked, graded, ledgered
E2  SKIP-NEEDS-KEY hallucination trap needs a live model
E3  PASS-OFFLINE   injection logged, grading stayed normal, no prompt leak
E4  PASS           2 sessions x 5 questions = 10 valid entries, schema intact
E5  PASS           Gemini forced to fail -> fallback completed the run
```

Decision: **E2 stays SKIP, not PASS.** A mock grader cannot judge whether a
model refuses to invent a metric — claiming otherwise would be a retroactive
clean story, which is exactly what this card grades against. With
`GEMINI_API_KEY` set, E1–E3 flip to live mode (`mode: "live"` in
`work/outputs/coach_evals.json`).

---

## Session 5 — live mode, first honest failure

Set `GEMINI_API_KEY` and ran `evals.py` in live mode: **E2 FAIL**, and its
detail text was the *mock grader's* wording — meaning the "live" run had
quietly fallen back offline. E1/E3 still showed PASS because their checks only
counted ledger entries. Fixed structurally: **E1/E3 now assert the grader's
provider** (must be `gemini` or `groq`, never `mock`, in live mode). An eval
that can pass while the thing it tests never ran is a broken eval.

## Session 6 — the model name was dead

With the evals hardened, the real error surfaced in `coach_events.jsonl`:
**HTTP 404 — `gemini-2.0-flash` no longer exists** (the first two sessions had
blamed headings and "silent fallback" instead of the model, because HTTP
errors only logged the bare status line). Fixed diagnostics: failures now log
the response body. Called the models endpoint with the key, switched to
`gemini-3.8-flash` per Google's own replacement message.

## Session 7 — free-tier rate limit, and waiting instead of lying

E1 passed live, E2/E3 fell back to mock again. New error in the event log:
**HTTP 429 — quota exceeded**: E1's six calls emptied the per-minute window,
the next two got throttled and silently downgraded.

Changes:
- `call_llm` does **one patient 65s wait on 429 and retries** the same
  provider before considering fallback (logged as `provider_throttled`).
  Quiet downgrade on throttle is the silent-failure mode guardrail designs
  are meant to prevent.
- `coach.py` paces questions by 7s, spreading the 10 API calls of a
  5-question session across quota window boundaries instead of bursting
  into a 429 on camera.
- After repeated test runs exhausted even the per-day quota, added a
  **300s circuit breaker**: once Gemini hard-fails on quota, later calls go
  straight to Groq instead of sleeping 65s on every question.

Re-ran live: **E1–E5 all PASS**, E2 reading "invented metric scored 0 with
'not in my notes'". Receipts: `work/outputs/coach_evals.json` (`mode: "live"`).

---

## Session 8 — two independent reviewer passes, then fix

Asked two parallel reviewers to audit the code separately: one for
robustness/correctness, one for spec compliance and clean code. Between them
they filed ~35 findings; the ones I acted on, in order of severity:

- **Crash on live network timeout** (caught on camera mid-recording):
  `TimeoutError` from a socket read escaped `call_llm`'s except list and
  killed the session with a traceback. Now: catch-all around each provider
  call + graceful session stop when providers are down. Re-ran E1–E5 live:
  all PASS.
- **Non-atomic ledger writes** — a crash mid-write could truncate
  `coach_log.json`; now writes to a temp file and `os.replace`s, and a
  corrupt ledger is quarantined to `.corrupt` instead of silently wiped.
- **Windows cp1252 pipes** — topic headings contain `→`, so `--list-topics`
  and eval subprocesses could die on `UnicodeEncodeError`. Now reconfigures
  stdout/stderr to UTF-8 with `errors="replace"` at startup.
- **E5 was too soft**: its forced failure was a plain `RuntimeError`, so the
  429 wait/retry path was never exercised and a mock fallback could pass it.
  Now: force-fail raises a simulated HTTP 429 (test hook skips the real 65s
  sleep), and live E5 requires the fallback to land on **groq** specifically.
- Also fixed: `Ctrl+C` traceback, `{"question": null}` printing as the string
  "None", `int(float("inf"))` OverflowError in score coercion, uncaught
  `TimeoutExpired` aborting the eval suite, Gemini key moved from URL to
  header so it cannot leak into the event log, shared system-prompt constant
  (DRY), mock questions now unique within a run so E4's no-duplicate
  assertion is meaningful offline too.
- Groq-specific repairs from the same period: its edge blocks urllib's
  default user-agent (error 1010), and the old `llama-3.3-70b` model name was
  retired — current model is `openai/gpt-oss-120b`.

Full re-run after the fixes: **E1–E5 all PASS** (live).

---

## Deviations from the FL-06 spec (all documented, none silent)

1. **Ledger format.** Spec wrote "one JSON line per answer" and E4 as
   "exactly 10 lines". Implemented as a JSON **array** in `coach_log.json` so
   the receipt file is valid JSON for anyone loading it; E4 now asserts
   exactly 10 *entries*, no duplicate questions inside a session, with the
   spec's schema fields plus a `provider` column (added so live/mock
   provenance is auditable).
2. **Extra internal functions beyond the spec's 4 tools.** The spec's four
   tools map to `list_topics`, `read_section`, `generate_question`,
   `grade_answer`/`write_ledger`. On top of those the agent calls
   `read_ledger` and `weak_topics` (the latter delivers the spec's "finds the
   concepts that stopped sticking" promise — it earns its place), and evals
   use `find_topic` for discovery. Six agent-reachable functions, not four.
3. **Notebooks dropped from the data sources.** The spec listed
   `notebooks/*.ipynb` markdown cells as a source; the whitelist covers the
   two curated docs + skills instead, because raw notebook cells are not
   clean quiz material. Not silent — listed here.
4. **Added `coach_events.jsonl`.** Not in the spec. It's the receipts file
   for provider fallback and guardrail events — without it, E5 has nothing to
   verify and the "silent failure" case would be invisible.
5. **E1 eval runs 3 questions**, session default stays 5 (spec) — keeps the
   harness fast; the ledger-integrity eval still exercises a full 5-question
   session twice.
6. **Cut from MVP:** the monthly/weekly weak-topic summary. Narrowest core
   job only, per FL-07 ("one full end-to-end run before adding anything").

## What broke / what I'd still do

- Broke: hardcoded heading match (S1), heading-level filter too narrow (S2),
  mock grading branch on the wrong prompt half (S3), dead model name (S6),
  quota-throttle fallback masking live failures (S7), TimeoutError crash on
  live networks + soft E5 (S8). All fixed and re-verified by re-running the
  exact command that caught each one.
- Live E1–E5: all passing (`mode: "live"` in `coach_evals.json`).
- Still pending: the 2-minute raw screen recording of a live session.
- Known limitation: in offline mode the deterministic model varies questions
  only by a drill counter; real mode varies them properly. Offline mode
  exists for the harness, not for study quality.
