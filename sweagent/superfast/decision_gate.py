"""Superfast Decision Gate -- System One front-door classifier (shadow mode).

Concept and reference implementation by Andrea Bruno, released under Creative
Commons Attribution 4.0 (CC BY 4.0). See the harness-superfast white paper at
https://github.com/Andrea-Bruno/harness-superfast. The decision models themselves
(Von, OpenJev, Laya) are third-party open models; only this integration
architecture and the routing method are part of the CC BY 4.0 work.

This is a faithful Python port of the reference decision gate. In a single
forward pass a small, fast, non-autoregressive "System One" decision model
answers a few typed questions about the pending turn, and this module turns those
answers into a conservative routing recommendation. It is built to be safe to
drop into an agent loop:

    Off by default. Nothing runs unless ``SUPERFAST_ENABLED`` is set to a truthy
    value. A user who does nothing sees the exact current behavior.

    Fail open. Any error, timeout, non-2xx response, unreachable backend, or
    malformed body yields "no opinion" (``None``). The gate never throws into the
    agent loop.

    No heavy dependencies. It talks to a local Jev-compatible HTTP endpoint with
    the ``requests`` client that SWE-agent already depends on. The decision model
    is installed out of band, never bundled.

    Shadow mode. The wired hook only logs the recommendation and its latency. It
    never changes routing, never skips the model call, and never alters any
    user-visible behavior. Acting on the route is a later, validated step.

The gate runs on a background thread so it adds no latency to the real turn.
"""

from __future__ import annotations

import math
import os
import threading
import time
from typing import Any

import requests

from sweagent.utils.log import get_logger

_logger = get_logger("swea-superfast", emoji="⚡")

#: Default Jev-compatible decision endpoint.
DEFAULT_ENDPOINT = "http://localhost:8000/v1/systemone"
#: Default decision model id sent in the request body.
DEFAULT_MODEL = "von-1.2.0"
#: Default hard timeout for a single decision call, in milliseconds.
DEFAULT_TIMEOUT_MS = 150

#: Values accepted as "on" for the ``SUPERFAST_ENABLED`` switch.
_TRUTHY = {"1", "true", "yes", "on"}

#: Standard question set for classifying an incoming turn. Kept small so the
#: single forward pass stays well under the timeout budget.
TURN_QUESTIONS: dict[str, dict[str, Any]] = {
    "needs_tool": {
        "type": "noul",
        "instructions": (
            "Does answering this request require taking an action with a tool "
            "(reading, writing, running, searching), rather than replying from "
            "what is already known?"
        ),
    },
    "answerable_from_context": {
        "type": "noul",
        "instructions": (
            "Can this request be answered from information already present in "
            "the conversation, without any new investigation?"
        ),
    },
    "intent": {
        "type": "choice",
        "instructions": "Classify the primary intent of the user request.",
        "criteria": {
            "code_change": "Create, edit, or delete code or files.",
            "code_question": "Explain or reason about code without changing it.",
            "command": "Run a command or operation.",
            "chat": "Casual conversation or a question needing no tools.",
            "other": "None of the above.",
        },
    },
}

#: Minimum calibrated intent confidence required for the plain_chat fast route.
PLAIN_CHAT_CONFIDENCE_FLOOR = 0.5


def _enabled() -> bool:
    """True only when ``SUPERFAST_ENABLED`` is set to a recognized truthy value."""
    return os.environ.get("SUPERFAST_ENABLED", "").strip().lower() in _TRUTHY


def _resolve_settings() -> dict[str, Any]:
    """Resolve gate settings from the environment, falling back to defaults."""
    raw_timeout = os.environ.get("SUPERFAST_TIMEOUT_MS", "")
    try:
        timeout_ms = int(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT_MS
    except ValueError:
        timeout_ms = DEFAULT_TIMEOUT_MS
    if timeout_ms <= 0:
        timeout_ms = DEFAULT_TIMEOUT_MS
    return {
        "endpoint": os.environ.get("SUPERFAST_ENDPOINT") or DEFAULT_ENDPOINT,
        "model": os.environ.get("SUPERFAST_MODEL") or DEFAULT_MODEL,
        "timeout_ms": timeout_ms,
    }


def _read_noul(answer: Any) -> float | None:
    """Return a noul probability only when it is a real finite value in [0, 1].

    Anything else (absent, NaN, Infinity, out of range, wrong type, or a bool)
    is treated as "no evidence" so an out-of-range or missing answer can never
    produce a decisive fast route.
    """
    if not isinstance(answer, dict):
        return None
    value = answer.get("noul")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if math.isfinite(value) and 0.0 <= value <= 1.0:
        return float(value)
    return None


def _confident(answer: Any, floor: float) -> bool:
    """True only for a real, finite confidence in [0, 1] at or above the floor."""
    if not isinstance(answer, dict):
        return False
    value = answer.get("confidence")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and 0.0 <= value <= 1.0 and value >= floor


def derive_route(answers: dict[str, Any]) -> str:
    """Derive a conservative route from the answers.

    The gate only recommends a fast route when the relevant probabilities are
    decisive; otherwise it says ``unknown`` so the caller falls back to the
    normal path.
    """
    needs_tool = _read_noul(answers.get("needs_tool"))
    from_context = _read_noul(answers.get("answerable_from_context"))

    # Decisive "needs a tool" wins first -- the harness must not skip work.
    if needs_tool is not None and needs_tool >= 0.85:
        return "needs_tool"

    # Strongly answerable from context, with a present and low tool-need signal.
    if from_context is not None and from_context >= 0.85 and needs_tool is not None and needs_tool <= 0.3:
        return "answer_from_context"

    # Clearly chat, with a calibrated intent and a present, low tool-need signal.
    intent = answers.get("intent")
    if (
        isinstance(intent, dict)
        and intent.get("choice") == "chat"
        and _confident(intent, PLAIN_CHAT_CONFIDENCE_FLOOR)
        and needs_tool is not None
        and needs_tool <= 0.2
    ):
        return "plain_chat"

    return "unknown"


def _query_system_one(
    state: str,
    questions: dict[str, Any],
    *,
    endpoint: str,
    model: str,
    timeout_ms: int,
) -> dict[str, Any] | None:
    """Issue one System One request.

    Returns the parsed ``answers`` on success, or ``None`` on any failure
    (fail-open). Never raises.
    """
    payload = {"model": model, "state": state, "questions": questions}
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout_ms / 1000.0)
    except Exception as exc:  # noqa: BLE001 -- fail open on any transport error
        _logger.debug("Decision gate unavailable (fail-open): %s", exc)
        return None
    if not resp.ok:
        _logger.debug("Decision gate non-2xx status=%s (fail-open)", resp.status_code)
        return None
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001 -- malformed body fails open
        _logger.debug("Decision gate malformed body (fail-open)")
        return None
    if not isinstance(data, dict):
        _logger.debug("Decision gate non-object body (fail-open)")
        return None
    answers = data.get("answers")
    if not isinstance(answers, dict):
        _logger.debug("Decision gate missing answers (fail-open)")
        return None
    return answers


def classify_turn(state: str) -> dict[str, Any] | None:
    """Classify a turn through the gate.

    Returns a dict with ``route``, ``answers`` and ``latency_ms`` on a clean
    answer, or ``None`` when the gate is disabled or unavailable (fail-open).
    """
    settings = _resolve_settings()
    started = time.perf_counter()
    answers = _query_system_one(
        state,
        TURN_QUESTIONS,
        endpoint=settings["endpoint"],
        model=settings["model"],
        timeout_ms=settings["timeout_ms"],
    )
    if answers is None:
        return None
    latency_ms = (time.perf_counter() - started) * 1000.0
    return {"route": derive_route(answers), "answers": answers, "latency_ms": latency_ms}


def _state_from_history(history: list[dict[str, Any]]) -> str:
    """Extract a plain-text state string from the last message of the history.

    Handles both string content and multimodal list content by joining any text
    blocks. Returns an empty string when there is nothing usable.
    """
    if not history:
        return ""
    last = history[-1]
    if not isinstance(last, dict):
        return ""
    content = last.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [block["text"] for block in content if isinstance(block, dict) and isinstance(block.get("text"), str)]
        return "\n".join(parts)
    return ""


def _shadow_worker(state: str) -> None:
    """Run the gate off the main thread and log the recommendation.

    Any failure is swallowed (fail-open) so the background thread can never
    disturb the agent.
    """
    try:
        decision = classify_turn(state)
    except Exception as exc:  # noqa: BLE001 -- shadow worker must never raise
        _logger.debug("Decision gate shadow worker failed (fail-open): %s", exc)
        return
    if decision is None:
        return
    _logger.info(
        "Superfast decision gate (shadow): route=%s latency_ms=%.1f",
        decision["route"],
        decision["latency_ms"],
    )


def shadow_gate(history: list[dict[str, Any]]) -> None:
    """Fire-and-forget shadow-mode hook for the agent loop.

    When the gate is disabled this returns immediately with no side effects. When
    enabled it extracts the current state and runs the gate on a daemon thread, so
    the real turn is never delayed. The result is only logged; routing is not
    changed.
    """
    if not _enabled():
        return
    state = _state_from_history(history)
    if not state:
        return
    thread = threading.Thread(target=_shadow_worker, args=(state,), daemon=True, name="superfast-gate")
    thread.start()
