# FL-10 build-in-public post (LinkedIn draft)

*One real decision + one real limitation, as the brief requires. Paste as-is, or trim.*

---

Eight weeks of FlyRank's AI internship, wrapped. Two things I built in public: an ML pipeline that ranks which of 30,000 production content pages should be refreshed first, and a terminal study-agent that quizzes me from my own notes. Both are in my repo, with the eval receipts.

**The design decision I'd make again:** group your validation split by the entity that appears in your features. My random forest looked like 0.757 AUC on a random split — then 0.603 the moment I held out entire clients. That 0.154 drop isn't a bug to hide, it's the actual result. I put it in the paper as a chart. If a client's traffic signature can leak into your features, a random split measures memorization, not generalization.

**The limitation I'm not hiding:** the study agent only reads three whitelisted files and refuses anything under data/. It will answer "not in my notes" far more often than a ChatGPT-style bot, and the weekly-summary feature from my spec got cut for the MVP — it doesn't exist. Free-tier API quotas also killed my first demo recording mid-run (the agent fell back to a second provider and survived — eval E5 proves the path — but fragile is fragile).

Honest numbers, runnable code, live paper: https://abdullah-9862873.github.io/FlyRank-Internship/
Repo: https://github.com/Abdullah-9862873/FlyRank-Internship

Grateful to the FlyRank crew for a program that insisted on baselines, limitations sections, and receipts at every step. On to the next build.
