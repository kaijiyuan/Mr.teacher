from __future__ import annotations
from enum import Enum
from typing import Any


class GuidanceMode(str, Enum):
    """Teaching style selected for the current turn."""

    SOCRATIC = "socratic"
    HEURISTIC = "heuristic"
    DIRECT = "direct"


class UnderstandingLevel(str, Enum):
    """Coarse assessment used by downstream quiz and review agents."""

    CONFUSED = "confused"
    PARTIAL = "partial"
    GOOD = "good"
    EXCELLENT = "excellent"


ConversationTurn = dict[str, Any]
