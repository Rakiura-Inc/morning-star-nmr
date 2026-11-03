"""Calls that must never stop a member's notebook."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def quietly(call: Callable[[], T], default: T) -> T:
    """call(), or default if it raises anything at all.

    Used around the optional Rakiura helper, IPython and git: whatever goes wrong there, the notebook
    keeps running in offline mode."""
    try:
        return call()
    except Exception:  # noqa: BLE001 (any failure in an optional extra falls back to the default)
        return default
