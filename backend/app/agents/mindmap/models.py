"""Data models for the mindmap agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MindmapNode:
    """A single node in the mindmap tree."""

    id: str
    title: str
    summary: str = ""
    children: list[MindmapNode] = field(default_factory=list)
    source_chunks: list[str] = field(default_factory=list)
    importance: int = 1  # 1-5


@dataclass
class KeyPoint:
    """A core knowledge point extracted from the document."""

    title: str
    description: str
    related_chunks: list[str] = field(default_factory=list)
    difficulty: int = 1  # 1-5


@dataclass
class MindmapResult:
    """Full mindmap output."""

    title: str
    nodes: list[MindmapNode]
    key_points: list[KeyPoint]
    document_id: str = ""
