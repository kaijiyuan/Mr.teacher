from __future__ import annotations
"""Data models for the file parser agent."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedChunk:
    """A single content chunk extracted from a parsed document."""

    text: str
    page: int = 0
    type: str = "text"  # text | table | formula | heading
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """Full result of parsing a document through MinerU."""

    file_name: str
    full_text: str
    chunks: list[ParsedChunk]
    page_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
