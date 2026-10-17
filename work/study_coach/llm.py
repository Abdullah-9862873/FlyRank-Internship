from __future__ import annotations

import io
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
GROQ_MODEL = "openai/gpt-oss-120b"
HTTP_TIMEOUT_SECONDS = 30
RATE_LIMIT_WAIT_SECONDS = 65  # free-tier quota windows reset per minute
GEMINI_BACKOFF_SECONDS = 300  # after a hard 429, stop burning waits for 5 min

# Circuit breaker: once Gemini hard-fails on quota, later calls go straight
# to the next provider instead of sleeping 65s on every single question.
_gemini_backoff_until = 0.0


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
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        # Tolerate GEMINI_API_KEY="..." and trailing comments in .env files.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1].strip()
        os.environ.setdefault(key.strip(), value)


def record_event(event: dict) -> None:
    # Best-effort telemetry: a failed write must never take the session down.
    try:
        EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except OSError:
        pass


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
        # Simulated quota failure: a real-shaped 429 so the wait/circuit/fallback
        # path is exercised by E5, not a plain RuntimeError that bypasses it.
        raise urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com/simulated",
            429,
            "simulated quota failure",
            {},
            io.BytesIO(b'{"error":{"message":"COACH_FORCE_GEMINI_FAIL=1"}}'),
        )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    # Key travels in a header, never the URL, so it cannot leak into logs.
    body = _post_json(url, {"x-goog-api-key": api_key}, payload)
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
    body = _post_json(
        url,
        {
            "Authorization": f"Bearer {api_key}",
            # Groq's edge blocks urllib's default "Python-urllib" agent (1010).
            "User-Agent": "flyrank-study-coach/1.0",
        },
        payload,
    )
    return body["choices"][0]["message"]["content"]


def call_mock(system_prompt: str, user_prompt: str) -> str:
    # Deterministic offline model: enough to exercise the full loop and E1/E4/E5
    # evals without a key.
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
    # Counter keeps mock questions unique inside one run so E4's no-duplicate
    # assertion stays meaningful in offline mode too.
    global _mock_question_number
    _mock_question_number += 1
    return json.dumps(
        {
            "question": (
                f"In one sentence, what is the single most important rule "
                f"my notes give about '{readable_topic}'? Answer with the rule, "
                f"not an example. (drill #{_mock_question_number})"
            )
        }
    )


_mock_question_number = 0


def call_llm(system_prompt: str, user_prompt: str) -> LlmReply:
    global _gemini_backoff_until
    attempts = (
        ("gemini", call_gemini),
        ("groq", call_groq),
        ("mock", call_mock),
    )
    failures: list[str] = []
    for provider, call in attempts:
        if provider == "gemini" and time.time() < _gemini_backoff_until:
            failures.append("gemini: skipped (recent quota 429, circuit breaker open)")
            continue
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
            except Exception as error:  # noqa: BLE001 - any provider failure must fall through, never crash the session
                detail = _error_detail(error)
                if (
                    isinstance(error, urllib.error.HTTPError)
                    and error.code == 429
                    and not rate_limited_once
                ):
                    # Quota window: one patient wait beats silent downgrade to mock.
                    # The E5 test hook skips the sleep - a simulated 429 must not
                    # cost a real minute of wall-clock time.
                    rate_limited_once = True
                    record_event({"provider_throttled": provider, "wait_seconds": RATE_LIMIT_WAIT_SECONDS})
                    if os.environ.get("COACH_FORCE_GEMINI_FAIL") != "1":
                        time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    continue
                failures.append(f"{provider}: {detail}")
                record_event({"provider_failed": provider, "error": detail})
                if provider == "gemini" and isinstance(error, urllib.error.HTTPError) and error.code == 429:
                    _gemini_backoff_until = time.time() + GEMINI_BACKOFF_SECONDS
                    record_event({"circuit_open": "gemini", "skip_seconds": GEMINI_BACKOFF_SECONDS})
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
