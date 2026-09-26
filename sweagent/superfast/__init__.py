"""Superfast Decision Gate package.

Concept and reference implementation by Andrea Bruno, CC BY 4.0. See
``decision_gate`` for the full design contract. The public entry point for the
agent loop is :func:`shadow_gate`.
"""

from __future__ import annotations

from sweagent.superfast.decision_gate import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_MS,
    TURN_QUESTIONS,
    classify_turn,
    derive_route,
    shadow_gate,
)

__all__ = [
    "DEFAULT_ENDPOINT",
    "DEFAULT_MODEL",
    "DEFAULT_TIMEOUT_MS",
    "TURN_QUESTIONS",
    "classify_turn",
    "derive_route",
    "shadow_gate",
]
