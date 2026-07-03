from __future__ import annotations
"""File parser agent — ingests documents via MinerU API, extracts chunks
and persists them into the KnowledgeService."""

import base64
import os
import tempfile
import uuid
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.agents.file_parser.models import ParsedChunk, ParseResult
from app.agents.file_parser.prompts import build_summary_prompt
from app.core.result import AgentResult, Artifact
from app.core.runtime import AgentRuntime
from app.services.knowledge import KnowledgeService
from app.services.mineru_client import MinerUClient


class FileParserAgent(BaseAgent):
    """Parses PDF documents using the MinerU API, extracts structured chunks
    and stores them into the KnowledgeService."""

    config = AgentConfig(
        id="file_parser",
        name="File Parser Agent",
        role="document_ingestor",
        description="Parses PDF files via MinerU API and builds a knowledge base.",
        input_keys=[
            "file_content",
            "file_name",
            "user_profile",
        ],
        output_keys=[
            "document_id",
            "knowledge_base_id",
            "document_metadata",
            "document_summary",
        ],
        required_services=["llm", "knowledge", "mineru"],
        priority=10,
        enabled=True,
        strict_inputs=True,
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        file_name: str = inputs.get("file_name", "unknown.pdf")
        file_content: str = inputs.get("file_content", "")
        _validate_pdf(file_name, file_content)

        # 1. Save decoded content to a temp file for MinerU upload
        temp_path = _save_temp_file(file_content, file_name)

        try:
            # 2. Parse via MinerU
            mineru: MinerUClient = runtime.services.get("mineru")
            parse_result = await mineru.parse_file(temp_path)

            # 3. Convert MinerU output into internal chunk representation
            parsed = self._convert_parse_result(parse_result, file_name)

            # 4. Optionally generate a summary via LLM
            knowledge: KnowledgeService = runtime.services.get("knowledge")
            summary = await self._generate_summary(parsed, runtime, inputs)

            # 5. Persist into KnowledgeService
            chunks_dict = [
                {
                    "text": c.text,
                    "page": c.page,
                    "type": c.type,
                    "metadata": c.metadata,
                }
                for c in parsed.chunks
            ]
            storage_result = await knowledge.add_document(
                file_name=file_name,
                text=parsed.full_text,
                chunks=chunks_dict,
                metadata=parsed.metadata,
            )

            document_id = storage_result["document_id"]
            knowledge_base_id = storage_result["knowledge_base_id"]

            metadata = {
                "file_name": file_name,
                "page_count": parsed.page_count,
                "chunk_count": len(parsed.chunks),
                "file_size": os.path.getsize(temp_path) if os.path.exists(temp_path) else 0,
            }

            return AgentResult(
                state_update={
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "document_metadata": metadata,
                    "document_summary": summary,
                },
                artifacts=[
                    Artifact(
                        type="document",
                        name=file_name,
                        content={
                            "document_id": document_id,
                            "summary": summary,
                            "metadata": metadata,
                        },
                        format="json",
                    ),
                ],
            )
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    # ── helpers ──────────────────────────────────────────────────────────

    def _convert_parse_result(
        self,
        mineru_result: dict[str, Any],
        file_name: str,
    ) -> ParseResult:
        """Convert the MinerU result dict into our internal ParseResult.

        The MinerU ``content_list`` is a list of blocks, each with a ``type``
        field (text, table, image, formula, etc.) and a ``text`` field.
        We flatten them into sorted chunks.
        """
        content_list = mineru_result.get("content_list", [])
        full_markdown = mineru_result.get("full_markdown", "")
        metadata = mineru_result.get("metadata", {})

        chunks: list[ParsedChunk] = []
        page_count = 0

        for block in content_list:
            block_type = block.get("type", "text")
            block_text = block.get("text", "").strip()
            if not block_text:
                continue

            # Map MinerU type to our internal type
            mapped_type = _map_mineru_type(block_type)

            # Extract page number if available
            page = block.get("page", block.get("page_idx", 0))

            chunk = ParsedChunk(
                text=block_text,
                page=page,
                type=mapped_type,
                metadata={"original_type": block_type},
            )
            chunks.append(chunk)

            # Track max page number
            if page > page_count:
                page_count = page

        # If no structured content_list, fall back to markdown heuristics
        if not chunks and full_markdown:
            chunks = self._fallback_chunk_markdown(full_markdown)
            page_count = 1

        # Build full text from chunks
        full_text = "\n\n".join(c.text for c in chunks)

        return ParseResult(
            file_name=file_name,
            full_text=full_text or full_markdown,
            chunks=chunks,
            page_count=page_count + 1,  # 0-indexed → 1-indexed count
            metadata={
                **metadata,
                "source_blocks": len(content_list),
            },
        )

    def _fallback_chunk_markdown(self, markdown: str) -> list[ParsedChunk]:
        """Heuristic chunking: split markdown by double newlines."""
        paragraphs = [p.strip() for p in markdown.split("\n\n") if p.strip()]
        chunks = []
        for i, para in enumerate(paragraphs):
            chunk_type = "heading" if para.startswith("#") else "text"
            chunks.append(ParsedChunk(text=para, page=0, type=chunk_type))
        return chunks

    async def _generate_summary(
        self,
        parsed: ParseResult,
        runtime: AgentRuntime,
        inputs: dict[str, Any],
    ) -> str:
        """Generate a document summary via LLM.

        If the LLM call fails, returns a brief fallback summary.
        """
        try:
            prompt = build_summary_prompt(parsed.full_text)
            response = await self.call_llm(runtime, prompt)
            return self._coerce_text(response)
        except Exception:
            return f"文档「{parsed.file_name}」已成功解析，共 {len(parsed.chunks)} 个内容块，{parsed.page_count} 页。"

    @staticmethod
    def _coerce_text(response: Any) -> str:
        """Extract string content from various LLM response formats."""
        if isinstance(response, str):
            return response
        if hasattr(response, "content"):
            return response.content
        if isinstance(response, dict) and "content" in response:
            return response["content"]
        return str(response)


# ── module-level helpers ─────────────────────────────────────────────────


def _validate_pdf(file_name: str, file_content: str) -> None:
    """Basic validation: check file extension and non-empty content."""
    if not file_name.lower().endswith(".pdf"):
        raise ValueError(f"Unsupported file type: {file_name}. Only PDF files are supported.")
    if not file_content:
        raise ValueError("file_content is empty.")


def _save_temp_file(file_content: str, file_name: str) -> str:
    """Decode base64 content and save to a temporary file.

    Accepts both raw base64 and ``data:application/pdf;base64,`` prefixed
    strings.
    """
    if file_content.startswith("data:"):
        # data URI scheme
        _, encoded = file_content.split(",", 1)
    else:
        encoded = file_content

    try:
        decoded = base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError("file_content is not valid base64.") from exc

    tmp_dir = tempfile.gettempdir()
    # Use a unique name to avoid collisions
    unique_name = f"fileparser_{uuid.uuid4().hex[:8]}_{file_name}"
    tmp_path = os.path.join(tmp_dir, unique_name)

    with open(tmp_path, "wb") as f:
        f.write(decoded)

    return tmp_path


def _map_mineru_type(mineru_type: str) -> str:
    """Map MinerU content types to our internal chunk types."""
    mapping = {
        "text": "text",
        "title": "heading",
        "table": "table",
        "image": "image",
        "chart": "image",
        "figure": "image",
        "formula": "formula",
        "interline_equation": "formula",
        "inline_equation": "formula",
        "list": "text",
        "header": "text",
        "footer": "text",
        "footnote": "text",
        "caption": "text",
    }
    return mapping.get(mineru_type, "text")
