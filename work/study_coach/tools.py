from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from llm import call_llm, record_event

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO_ROOT / "work" / "outputs" / "coach_log.json"
SECTION_CHAR_LIMIT = 4000

# Read whitelist: study material only. data/ is deliberately absent - datasets
# must never enter the agent (FL-06 guardrail).
READABLE_DOCS = [
    REPO_ROOT / "docs" / "data-dictionary.md",
    REPO_ROOT / "docs" / "ml-intern-dataset-and-lane-guide.md",
]
READABLE_SKILL_DIRS = [REPO_ROOT / "skills"]

LEDGER_FIELDS = {"ts", "topic", "question", "score", "provider"}


class GuardrailRefusal(Exception):
    pass


def _is_readable(path: Path) -> bool:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        return False
    if resolved.is_relative_to(REPO_ROOT / "data"):
        return False
    if resolved in [doc.resolve() for doc in READABLE_DOCS]:
        return True
    return any(
        resolved.is_relative_to(directory) and resolved.suffix == ".md"
        for directory in READABLE_SKILL_DIRS
    )


def list_topics() -> list[str]:
    topics: list[str] = []
    for path in READABLE_DOCS:
        topics.extend(_headings_of(path))
    for directory in READABLE_SKILL_DIRS:
        for skill_file in sorted(directory.glob("*/SKILL.md")):
            topics.extend(_headings_of(skill_file))
    return topics


def find_topic(fragment: str) -> str | None:
    fragment_lower = fragment.lower()
    for topic in list_topics():
        if fragment_lower in topic.lower():
            return topic
    return None


def _headings_of(path: Path) -> list[str]:
    if not path.exists():
        return []
    topics = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{2,3})\s+(.*)$", line)
        if match:
            heading = match.group(2).strip()
            topics.append(f"{path.relative_to(REPO_ROOT).as_posix()}#{heading}")
    return topics


def read_section(topic_id: str) -> str:
    if "#" not in topic_id:
        raise GuardrailRefusal(f"malformed topic id: {topic_id!r}")
    relative_path, heading = topic_id.rsplit("#", 1)
    path = (REPO_ROOT / relative_path).resolve()
    if not _is_readable(path):
        raise GuardrailRefusal(f"refused read outside whitelist: {relative_path}")
    if not path.exists():
        raise GuardrailRefusal(f"unknown document: {relative_path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")
    start = None
    level = 0
    for index, line in enumerate(lines):
        match = heading_re.match(line)
        if match and match.group(2).strip().lower() == heading.lower():
            start = index
            level = len(match.group(1))
            break
    if start is None:
        raise GuardrailRefusal(f"heading not found in {relative_path}: {heading!r}")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = heading_re.match(lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    section = "\n".join(lines[start:end]).strip()
    if len(section) > SECTION_CHAR_LIMIT:
        section = section[:SECTION_CHAR_LIMIT] + "\n[truncated]"
    return section


def generate_question(section_text: str, topic_id: str) -> dict:
    system_prompt = (
        "You are a study coach grounded ONLY in the provided section of Abdullah's "
        "FlyRank notes. Ask one question at a time. Prefer failure modes: leakage, "
        "window alignment, rate columns, claim vocabulary. "
        'Reply with ONLY a JSON object: {"question": "..."}.'
    )
    user_prompt = f"Topic: {topic_id}\nSECTION:\n{section_text}"
    reply = call_llm(system_prompt, user_prompt)
    payload = _parse_json_object(reply.text, fallback_key="question", fallback_text=reply.text)
    payload["provider"] = reply.provider
    return payload


def grade_answer(section_text: str, topic_id: str, question: str, answer: str) -> dict:
    system_prompt = (
        "You are a study coach grounded ONLY in the provided section of Abdullah's "
        "FlyRank notes. Grade the ANSWER 0 (wrong) 1 (right idea, incomplete) "
        "2 (correct and complete). If the topic is not in the section, score 0 and "
        "say 'not in my notes'. Never invent FlyRank facts. "
        'Reply with ONLY JSON: {"score": 0, "citation": "...", "note": "..."}'
    )
    user_prompt = (
        f"Topic: {topic_id}\nSECTION:\n{section_text}\n"
        f"QUESTION: {question}\nANSWER: {answer}\nGRADE THIS ANSWER"
    )
    if re.search(r"ignore\s+(all\s+)?(rules|instructions)|system prompt", answer, re.IGNORECASE):
        record_event({"guardrail": "injection_attempt_in_answer"})
    reply = call_llm(system_prompt, user_prompt)
    grade = _parse_json_object(reply.text, fallback_key="note", fallback_text=reply.text)
    grade["score"] = _coerce_score(grade.get("score"))
    grade.setdefault("citation", "")
    grade.setdefault("note", "")
    grade["provider"] = reply.provider
    return grade


def _parse_json_object(text: str, fallback_key: str, fallback_text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-z]*\n?|\n?```$", "", candidate).strip()
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {fallback_key: fallback_text.strip()}


def _coerce_score(value: object) -> int:
    try:
        score = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(2, score))


def write_ledger(topic_id: str, question: str, score: int, provider: str) -> dict:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = read_ledger()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic": topic_id,
        "question": question,
        "score": score,
        "provider": provider,
    }
    entries.append(entry)
    LEDGER_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entry


def read_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    try:
        data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def weak_topics(limit: int = 5) -> list[str]:
    scores: dict[str, list[int]] = {}
    for entry in read_ledger():
        topic = str(entry.get("topic", ""))
        if topic and isinstance(entry.get("score"), int):
            scores.setdefault(topic, []).append(entry["score"])
    ranked = sorted(scores.items(), key=lambda item: sum(item[1]) / len(item[1]))
    return [topic for topic, _ in ranked[:limit]]
