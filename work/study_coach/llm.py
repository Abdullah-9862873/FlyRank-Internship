from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVENTS_PATH = REPO_ROOT / "work" / "outputs" / "coach_events.jsonl"

GEMINI_MODEL = "gemini-3.8-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
HTTP_TIMEOUT_SECONDS = 30
RATE_LIMIT_WAIT_SECONDS = 65  # free-tier quota windows reset per minute


@dataclass
class LlmReply:
    text: str
    provider: str
    fallback_reason: str | None = None


def load_env_file() -> None:
    # Minimal .env reader so the agent runs without extra dependencies.
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def record_event(event: dict) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def call_gemini(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    if os.environ.get("COACH_FORCE_GEMINI_FAIL") == "1":
        raise RuntimeError("simulated Gemini failure (COACH_FORCE_GEMINI_FAIL=1)")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    body = _post_json(url, {}, payload)
    return body["candidates"][0]["content"]["parts"][0]["text"]


def call_groq(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    body = _post_json(url, {"Authorization": f"Bearer {api_key}"}, payload)
    return body["choices"][0]["message"]["content"]


def call_mock(system_prompt: str, user_prompt: str) -> str:
    # Deterministic offline model: enough to exercise the full loop and E1/E4/E5
    # evals without a key. Grade heuristic = "answers longer than 5 words earn 1".
    if "GRADE THIS ANSWER" in user_prompt:
        answer_block = user_prompt.split("\nANSWER:", 1)[-1]
        answer = answer_block.split("\nGRADE THIS ANSWER")[0].strip()
        if len(answer.split()) < 3:
            score = 0
        elif len(answer.split()) < 8:
            score = 1
        else:
            score = 2
        return json.dumps(
            {
                "score": score,
                "citation": "mock grader (offline mode - no notes citation)",
                "note": "offline grading: run with GEMINI_API_KEY for real citations",
            }
        )
    topic = "the section"
    if "Topic:" in user_prompt:
        topic = user_prompt.split("Topic:", 1)[1].strip().splitlines()[0]
    if "not-in-notes" in topic:
        return json.dumps({"question": "What does my notes say about this topic?"})
    readable_topic = topic.rsplit("#", 1)[-1]
    return json.dumps(
        {
            "question": (
                f"In one sentence, what is the single most important rule "
                f"my notes give about '{readable_topic}'? Answer with the rule, "
                f"not an example."
            )
        }
    )


def call_llm(system_prompt: str, user_prompt: str) -> LlmReply:
    attempts = (
        ("gemini", call_gemini),
        ("groq", call_groq),
        ("mock", call_mock),
    )
    failures: list[str] = []
    for provider, call in attempts:
        rate_limited_once = False
        while True:
            try:
                text = call(system_prompt, user_prompt)
                record_event(
                    {
                        "provider": provider,
                        "fallback_reason": failures[-1] if failures else None,
                        "waited_on_rate_limit": rate_limited_once,
                    }
                )
                return LlmReply(
                    text=text,
                    provider=provider,
                    fallback_reason=failures[-1] if failures else None,
                )
            except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, KeyError, json.JSONDecodeError) as error:
                detail = _error_detail(error)
                if (
                    isinstance(error, urllib.error.HTTPError)
                    and error.code == 429
                    and not rate_limited_once
                ):
                    # Quota window: one patient wait beats silent downgrade to mock.
                    rate_limited_once = True
                    record_event({"provider_throttled": provider, "wait_seconds": RATE_LIMIT_WAIT_SECONDS})
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    continue
                failures.append(f"{provider}: {detail}")
                record_event({"provider_failed": provider, "error": detail})
                break
    raise RuntimeError("all providers failed: " + " | ".join(failures))


def _error_detail(error: Exception) -> str:
    detail = str(error)
    if isinstance(error, urllib.error.HTTPError):
        try:
            detail = f"{error} :: {error.read().decode('utf-8')[:200]}"
        except Exception:  # noqa: BLE001 - body read is best-effort diagnostics
            pass
    return detail
