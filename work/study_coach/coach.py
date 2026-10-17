from __future__ import annotations

import argparse
import os
import sys
import time

from llm import load_env_file
from tools import (
    GuardrailRefusal,
    LEDGER_PATH,
    generate_question,
    grade_answer,
    list_topics,
    read_section,
    weak_topics,
    write_ledger,
)

DEFAULT_QUESTION_COUNT = 5
# Free Gemini tier throttles per-minute; pacing spreads requests so a
# 5-question session (10 API calls) smooths across quota window boundaries
# instead of bursting and hitting a 429 on camera.
PAUSE_BETWEEN_QUESTIONS_SECONDS = 7


def configure_console() -> None:
    # Windows pipes default to cp1252, which cannot encode note text like "→"
    # and kills the session (and every eval subprocess) with UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FlyRank study coach - quiz me from my own notes")
    parser.add_argument("--topic", help="Topic id as printed by --list-topics")
    parser.add_argument("--questions", type=int, default=DEFAULT_QUESTION_COUNT)
    parser.add_argument("--list-topics", action="store_true", help="Print available topics and exit")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Offline mode: ignore API keys, use the deterministic local model",
    )
    return parser.parse_args()


def choose_topic(requested: str | None) -> str:
    if requested:
        return requested
    backlog = weak_topics()
    if backlog:
        return backlog[0]
    topics = list_topics()
    if not topics:
        raise SystemExit("No readable topics found - is the repo checkout complete?")
    return topics[0]


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return "quit"


def run_session(topic_id: str, question_count: int, mock: bool = False) -> int:
    section_text = read_section(topic_id)
    print(f"\nTopic: {topic_id}")
    print(f"Notes loaded: {len(section_text)} chars\n")

    total = 0
    warned_mock = False
    for number in range(1, question_count + 1):
        try:
            question_payload = generate_question(section_text, topic_id)
        except RuntimeError as failure:
            print(f"  ! model providers unavailable: {failure}")
            break
        question = str(question_payload.get("question", "") or "").strip()
        if not question:
            print("  ! no question generated - stopping early")
            break
        if not mock and not warned_mock:
            if question_payload.get("provider") == "mock":
                print("  ! WARNING: live providers unreachable, falling back to mock grader")
                warned_mock = True
        print(f"Q{number}/{question_count}: {question}")
        answer = ask("  your answer> ")
        if answer.lower() in {"quit", "q", "exit"}:
            print("Session ended early - logged answers stay in the ledger.")
            break
        try:
            grade = grade_answer(section_text, topic_id, question, answer)
        except RuntimeError as failure:
            print(f"  ! could not grade this answer (providers down): {failure}")
            print("  Answered entries so far stay in the ledger.")
            break
        score = int(grade["score"])
        total += score
        write_ledger(topic_id, question, score, str(grade.get("provider", "unknown")))
        print(f"  score {score}/2 - {str(grade.get('note', '') or '')}")
        if grade.get("citation"):
            print(f"  notes: {grade['citation']}")
        print()
        if number < question_count and not mock:
            time.sleep(PAUSE_BETWEEN_QUESTIONS_SECONDS)

    print(f"Session done. Points: {total}/{question_count * 2}")
    print(f"Ledger: {LEDGER_PATH.relative_to(LEDGER_PATH.parents[2]).as_posix()}")
    return 0


def main() -> int:
    configure_console()
    args = parse_args()
    load_env_file()
    if args.mock:
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GROQ_API_KEY", None)

    if args.list_topics:
        for topic in list_topics():
            print(topic)
        return 0

    if args.questions < 1 or args.questions > 20:
        raise SystemExit("--questions must be between 1 and 20")

    try:
        topic_id = choose_topic(args.topic)
        return run_session(topic_id, args.questions, mock=args.mock)
    except GuardrailRefusal as refusal:
        print(f"Guardrail: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted - answered entries stay in the ledger.", file=sys.stderr)
        raise SystemExit(130)
