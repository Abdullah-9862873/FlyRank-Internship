# The plan to keep building — where the next case study goes

 Written 2026-10-18, while everything is still fresh. Re-read this before the next case, not from memory.

## Where the next case study goes

**On the site:** Portfolio_Site → `ThingsBuilt` section — a new card linking to its own page
(`Portfolio_Site` repo, one markdown-driven page or component per case, same look as the rest).
**In the repo:** the work itself lives in `FlyRank-Internship` (or its own repo if it outgrows this one),
with the case-study write-up committed next to the code.
**On the track index:** one row in `work/FL_TRACK_INDEX.md`.

## The named next piece of work

**Study Coach v2 — the weekly summary + spaced-repetition scheduler.**
The FL-06 spec had it; the MVP cut it (README limitation #2, retrospective "what you'd build next").
The ledger (`work/outputs/coach_log.json`) already logs every answer — v2 reads that ledger,
ranks topics by miss rate + decay since last seen, and opens each session on the three due-est topics
instead of just the weakest. One real feature, one real repo, one honest limitation to fix.

**Reminder set:** scheduled GitHub Action (`.github/workflows/reminder-study-coach-v2.yml`)
opens a repo issue on **2026-11-15, 09:00 UTC** — "Study Coach v2: build the spaced-repetition
scheduler and write the case study." The issue is the nudge; GitHub emails it to you.
Backup nudge: phone calendar event, 2026-11-15, recurring yearly is overkill — one-shot is enough.

## Steps to add any future case study (the Week 2 three-beat shape)

1. **Problem (2–3 sentences).** What was broken or missing, for whom, in plain words. One real
   scenario beats three abstractions — the FlyRank refresh-triage dilemma was mine.
2. **What I did (the middle).** Tools, the one design decision you'd defend, the eval or check
   that proved it worked. Name the honest number, including the unflattering one
   (the 0.154 memorization gap is why people trusted the paper).
3. **What came of it (the end).** Measured outcome, what you'd do next, one known limitation.
   Link the receipts (eval json, paper URL, live demo) — a link beats an adjective.

Then, mechanically: draft the three beats as markdown in the repo → add one figure or screenshot →
new card in `ThingsBuilt` linking to it → `npm run build` passes → push (Netlify auto-deploys) →
add a row to `FL_TRACK_INDEX.md` → one build-in-public post with the link.

**Keep it cheap:** the build context is preserved — this repo's `AGENTS.md`, `skills/`,
and your assistant's working knowledge of your voice, stack, and identity kit (portfolio,
paper, coach). The next case is a short conversation pointing at this note, not a rebuild.
