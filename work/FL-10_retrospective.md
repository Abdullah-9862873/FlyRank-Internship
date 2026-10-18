# FL-10 retrospective — a letter to Week-1 me

*Written 2026-10-18, for the person starting this internship on July 1. About 650 words.*

---

Hey. You're about to spend eight weeks building things you'll actually show people, and I want to save you some of the wrong turns — without stealing the useful ones.

**What you set out to do:** learn "AI engineering" in the vague way job descriptions say it. You wanted a capstone with your name on it, some certificates, and the feeling of having shipped something real. That's fine as a goal, but it's not the thing that will matter.

**What actually happened, in order.** You built an ML pipeline on real production search data — 30,000 pages, 32 clients — and the first number your model produced was a random-split AUC of 0.757. It felt great for about a day, until validation forced you to group the split by client and the number fell to 0.603. That 0.154 collapse was the single most valuable result of the whole internship, because it taught you the difference between a demo and a claim. You then wrote a paper that leads with the weak number, shows the gap as a chart, and still ships a usable artifact: a ranked refresh queue with reason codes that a content team could open every Monday. You also built a study agent that quizzes you from your own notes — small, boring, honest, all five evals passing live, with a fallback path that survived your first demo recording getting killed by a Gemini rate limit.

**What changed in how you work — specifically, not generically.** Three things, and they're transferable to any job you take after this:

1. **Evals before build.** You wrote the five test cases for the study agent before writing the agent. When a silent bug made every offline grade come back 0 while the eval counters stayed green, the harness is what let you catch it instead of shipping it. Now you'll demand this of everything: define "works" first, then build "working."

2. **The honest number is a feature.** The memorization gap, the non-monotonic decay finding, the limitations section you wrote before anyone asked — reviewers trusted the work *because* you buried the flattering story. You'll never again report a metric without naming the split it came from.

3. **Receipts or it didn't happen.** Every session, eval, and claim in this internship traces to a file: coach_evals.json, playbook_metrics.json, capstone.ipynb outputs. When someone asks "how do you know?", you send a link instead of an adjective. This is now just how you work.

**What you'd build next, given a free week.** The study agent's weekly summary feature you cut for the MVP — a real spaced-repetition scheduler over the ledger you already log. Then a tiny web front-end so it's not terminal-only. And on the ML side: time-based validation the moment someone hands you a second data snapshot, because a single cross-section can't answer "will this still work in March?"

**What to worry less about.** The certificates. The perfect portfolio polish. Whether AI "did the work" — it drafted plenty of code, and you verified all of it with runs, evals, and hand-testing; that division of labor is the job now, not a caveat. The people who finish this are the ones who ship honest things on time, not the ones with the fanciest models.

**One warning, since you'll be tempted.** Week 3-ish you'll want to skip validation because the first results look good. Don't. The gap between 0.757 and 0.603 is exactly the size of the temptation, and catching it is what makes the rest of this portfolio defensible in an interview.

You're going to finish this with a deployed paper, a working agent, a hardened portfolio site, and a story you can tell in five minutes. Not bad for eight weeks of learning to ask better questions of your own work.

— Future you, October 2026
