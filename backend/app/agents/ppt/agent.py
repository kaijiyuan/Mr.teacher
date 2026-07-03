from __future__ import annotations

import json
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.agents.ppt.builder import build_pptx
from app.agents.ppt.models import PptOutline, Slide
from app.agents.ppt.prompts import GENERATE_PPT_OUTLINE_PROMPT, GENERATE_PPT_SUMMARY_PROMPT
from app.core.result import AgentResult, Artifact
from app.core.runtime import AgentRuntime


class PPTAgent(BaseAgent):
    """根据知识库内容和学习画像生成复习 PPT 大纲。"""

    config = AgentConfig(
        id="ppt",
        name="PPT Agent",
        role="review_material_builder",
        description="根据知识库检索结果、核心知识点和答题评估生成 PPT 复习大纲。",
        input_keys=[
            "knowledge_base_id",
            "topic",
            "slide_count",
            "user_profile",
            "key_points",
            "quiz_evaluation",
        ],
        output_keys=[
            "ppt_artifact_id",
            "ppt_outline",
            "ppt_file_path",
        ],
        required_services=["llm", "knowledge"],
        priority=40,
        enabled=True,
        strict_inputs=False,
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        knowledge_svc = runtime.get_service("knowledge")

        topic = inputs.get("topic", "")
        kb_id = inputs.get("knowledge_base_id", "")

        # 1. 从知识库检索相关内容
        knowledge_context = ""
        if kb_id:
            try:
                search_results = await knowledge_svc.search(
                    knowledge_base_id=kb_id,
                    query=topic,
                    top_k=5,
                    mode="hybrid",
                )
                knowledge_context = "\n\n".join(
                    r.get("text", "") for r in search_results if r.get("text")
                )
            except Exception as e:
                print(f"[PPTAgent] Knowledge search failed: {e}")

        # 2. 准备 key_points 文本
        key_points = inputs.get("key_points", [])
        key_points_text = ""
        if key_points:
            if isinstance(key_points, list):
                key_points_text = "\n".join(
                    f"- {kp.get('title', kp) if isinstance(kp, dict) else kp}"
                    for kp in key_points
                )
            else:
                key_points_text = str(key_points)

        # 3. 准备 weak_points（来自 QuizEvaluation）
        quiz_evaluation = inputs.get("quiz_evaluation", {})
        weak_points = quiz_evaluation.get("weak_points", []) if isinstance(quiz_evaluation, dict) else []
        weak_points_text = "\n".join(f"- {wp}" for wp in weak_points) if weak_points else "无"

        # 4. 拼装 Prompt 生成大纲
        outline_prompt = GENERATE_PPT_OUTLINE_PROMPT.format(
            topic=topic,
            slide_count=inputs.get("slide_count", 10),
            key_points=key_points_text or "无",
            knowledge_context=knowledge_context or "无参考资料，请基于常识生成。",
            weak_points=weak_points_text,
        )

        raw_response = await self.call_llm(runtime, outline_prompt)
        response_text = self._coerce_text(raw_response)
        slides_data = self._parse_slides(response_text)

        # 5. 生成整体摘要
        summary = ""
        try:
            slides_json = json.dumps(slides_data, ensure_ascii=False)
            summary_prompt = GENERATE_PPT_SUMMARY_PROMPT.format(
                title=topic,
                outline=slides_json[:3000],
            )
            summary_raw = await self.call_llm(runtime, summary_prompt)
            summary = self._coerce_text(summary_raw).strip()
        except Exception as e:
            print(f"[PPTAgent] Summary generation failed: {e}")

        # 6. 构建输出
        outline = PptOutline(
            title=topic,
            slides=[Slide(**s) if not isinstance(s, Slide) else s for s in slides_data],
            slide_count=len(slides_data),
            topic=topic,
            summary=summary,
        )
        outline_dict = {
            "title": outline.title,
            "slides": [
                {
                    "title": s.title,
                    "bullets": s.bullets,
                    "speaker_notes": s.speaker_notes,
                    "source_chunks": s.source_chunks,
                }
                for s in outline.slides
            ],
            "slide_count": outline.slide_count,
            "topic": outline.topic,
            "summary": outline.summary,
        }
        artifact_id = f"ppt__{outline.title.lower().replace(' ', '_')[:32]}"

        # 7. 生成 .pptx 文件
        ppt_file_path = ""
        try:
            ppt_file_path = build_pptx(outline_dict)
        except Exception as e:
            print(f"[PPTAgent] PPTX build failed: {e}")

        return AgentResult(
            state_update={
                "ppt_artifact_id": artifact_id,
                "ppt_outline": outline_dict,
                "ppt_file_path": ppt_file_path,
            },
            artifacts=[
                Artifact(
                    type="ppt_outline",
                    name=artifact_id,
                    content=outline_dict,
                    format="json",
                ),
            ],
            messages=[{"role": "assistant", "content": f"已生成 {len(outline.slides)} 页 PPT 大纲。"}],
        )

    # ── helpers ─────────────────────────────────────────────────────

    def _parse_slides(self, text: str) -> list[dict]:
        """从 LLM 返回文本中提取 JSON 幻灯片数组。"""
        text = text.strip()

        # 解包 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("```") and i > 0:
                    end = i
                    break
            text = "\n".join(lines[start:end])
            text = text.strip()

        # 尝试直接解析
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "slides" in data:
                return data["slides"]
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 数组
        try:
            idx = text.index("[")
            end_idx = text.rindex("]") + 1
            data = json.loads(text[idx:end_idx])
            if isinstance(data, list):
                return data
        except (ValueError, json.JSONDecodeError):
            pass

        print(f"[PPTAgent] Failed to parse slides from LLM response: {text[:200]}")
        return []

    def _coerce_text(self, value: Any) -> str:
        """将 LLM 响应统一转为文本。"""
        if isinstance(value, str):
            return value
        content = getattr(value, "content", None)
        if content is not None:
            return str(content)
        choices = getattr(value, "choices", None)
        if choices:
            first_choice = choices[0]
            delta = getattr(first_choice, "delta", None)
            delta_content = getattr(delta, "content", None)
            if delta_content is not None:
                return str(delta_content)
            message = getattr(first_choice, "message", None)
            message_content = getattr(message, "content", None)
            if message_content is not None:
                return str(message_content)
        if isinstance(value, dict):
            if "content" in value:
                return str(value["content"])
            if "text" in value:
                return str(value["text"])
        return str(value)
