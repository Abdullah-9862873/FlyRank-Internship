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

## Deviations from the FL-06 spec (all documented, none silent)

1. **Ledger format.** Spec wrote "one JSON line per answer" and E4 as
   "exactly 10 lines". Implemented as a JSON **array** in `coach_log.json` so
   the receipt file is valid JSON for anyone loading it; E4 now asserts
   exactly 10 *entries* with the same schema fields.
2. **Two extra internal functions.** `generate_question` split out of the
   grading path (one thing per function), plus `read_ledger`/`weak_topics` —
   the latter is what actually delivers the spec's "finds the concepts that
   stopped sticking" promise, so it earned its place.
3. **Added `coach_events.jsonl`.** Not in the spec. It's the receipts file
   for provider fallback and guardrail events — without it, E5 has nothing to
   verify and the "silent failure" case would be invisible.
4. **E1 eval runs 3 questions**, session default stays 5 (spec) — keeps the
   harness fast; the ledger-integrity eval still exercises a full 5-question
   session twice.
5. **Cut from MVP:** the monthly/weekly weak-topic summary. Narrowest core
   job only, per FL-07 ("one full end-to-end run before adding anything").

## What broke / what I'd still do

- Broke: hardcoded heading match (S1), heading-level filter too narrow (S2),
  mock grading branch on the wrong prompt half (S3). All three fixed and
  re-verified by re-running the same command that caught them.
- Still pending until capture: live E1–E3 (needs `GEMINI_API_KEY` at run
  time) and the 2-minute raw screen recording of a live session.
- Known limitation: in offline mode the deterministic model repeats the same
  question template within a session. Real mode varies questions; offline mode
  exists for the harness, not for study quality.
