"""Mindmap agent — generates a structured knowledge tree from a document."""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.agents.mindmap.models import KeyPoint, MindmapNode, MindmapResult
from app.agents.mindmap.prompts import MINDMAP_SYSTEM, build_mindmap_prompt
from app.core.result import AgentResult, Artifact
from app.core.runtime import AgentRuntime


class MindmapAgent(BaseAgent):
    """Generates a hierarchical mindmap from knowledge-base content."""

    config = AgentConfig(
        id="mindmap",
        name="Mindmap Agent",
        role="knowledge_structurer",
        description="从知识库检索内容，生成层次化思维导图和核心知识点。",
        input_keys=[
            "document_id",
            "knowledge_base_id",
            "document_summary",
            "user_profile",
        ],
        output_keys=["mindmap", "key_points", "document_summary"],
        required_services=["llm", "knowledge"],
        priority=20,
        enabled=True,
        strict_inputs=False,
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        document_id = str(inputs.get("document_id", ""))
        kb_id = str(inputs.get("knowledge_base_id", ""))
        doc_summary = str(inputs.get("document_summary", ""))

        # 1. Retrieve chunks from knowledge base (use TF mode to get all chunks)
        knowledge = runtime.get_service("knowledge")
        # Get all chunks by using an empty-ish query with TF mode
        chunks = await knowledge.search(
            knowledge_base_id=kb_id,
            query=doc_summary or ".",
            top_k=40,
            mode="tf",
        )

        if not chunks:
            return AgentResult(
                state_update={
                    "mindmap": None,
                    "key_points": [],
                    "document_summary": doc_summary,
                },
                messages=[{"role": "system", "content": "知识库中没有可用的内容块。"}],
            )

        # 2. Build context from chunks
        context_parts = []
        for i, c in enumerate(chunks, 1):
            context_parts.append(f"[{i}] (第{c.get('page', '?')}页) {c['text']}")
        knowledge_context = "\n\n".join(context_parts)

        # 3. Call LLM to generate mindmap
        prompt = build_mindmap_prompt(
            document_summary=doc_summary,
            knowledge_context=knowledge_context[:8000],
        )

        # Use a system message for better formatting
        llm_service = runtime.get_service("llm")
        raw = llm_service.client.chat.completions.create(
            model=llm_service.model_name,
            messages=[
                {"role": "system", "content": MINDMAP_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            stream=False,
        )
        response = raw.choices[0].message.content

        # 4. Parse JSON response
        mindmap_data = self._parse_mindmap_json(response)
        if mindmap_data is None:
            return AgentResult(
                state_update={
                    "mindmap": None,
                    "key_points": [],
                    "document_summary": doc_summary,
                },
            )

        # 5. Build result
        mindmap = self._to_mindmap_dict(mindmap_data, document_id)

        return AgentResult(
            state_update={
                "mindmap": mindmap,
                "key_points": mindmap.get("key_points", []),
                "document_summary": mindmap.get("title", doc_summary),
            },
            artifacts=[
                Artifact(
                    type="mindmap",
                    name=f"mindmap_{document_id}",
                    content=mindmap,
                    format="json",
                )
            ],
        )

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _coerce_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        content = getattr(value, "content", None)
        if content is not None:
            return str(content)
        choices = getattr(value, "choices", None)
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg and hasattr(msg, "content"):
                return str(msg.content)
        return str(value)

    @staticmethod
    def _parse_mindmap_json(text: str) -> dict | None:
        """Extract and parse the mindmap JSON from LLM output."""
        # Remove code fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        # Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Try to find JSON block in the cleaned text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Try the original text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        print(f"[Mindmap] Failed to parse LLM output: {text[:300]}")
        return None

    @staticmethod
    def _to_mindmap_dict(data: dict, document_id: str) -> dict:
        """Convert raw LLM output to the standard mindmap dict."""
        nodes = []
        for node_data in data.get("nodes", []):
            nodes.append(MindmapAgent._convert_node(node_data))

        key_points = []
        for kp in data.get("key_points", []):
            key_points.append({
                "title": kp.get("title", ""),
                "description": kp.get("description", ""),
                "difficulty": kp.get("difficulty", 1),
            })

        return {
            "title": data.get("title", "文档思维导图"),
            "document_id": document_id,
            "nodes": nodes,
            "key_points": key_points,
        }

    @staticmethod
    def _convert_node(node_data: dict) -> dict:
        children = []
        for child in node_data.get("children", []):
            children.append(MindmapAgent._convert_node(child))
        return {
            "id": node_data.get("id", ""),
            "title": node_data.get("title", ""),
            "summary": node_data.get("summary", ""),
            "importance": node_data.get("importance", 1),
            "children": children,
        }
