from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.agents.quiz.prompts import GENERATE_QUIZ_PROMPT
from app.core.result import AgentResult, Artifact
from app.core.runtime import AgentRuntime


class QuizAgent(BaseAgent):
    """根据知识库内容和学习画像生成题目。"""

    config = AgentConfig(
        id="quiz",
        name="Quiz Agent",
        role="quiz_generator",
        description="根据知识库检索结果和核心知识点生成练习题。",
        input_keys=[
            "knowledge_base_id",
            "topic",
            "question_count",
            "question_types",
            "difficulty",
            "user_profile",
            "key_points",
        ],
        output_keys=[
            "questions",
            "quiz_session_id",
            "quiz_metadata",
        ],
        required_services=["llm", "knowledge"],
        priority=30,
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
                print(f"[QuizAgent] Knowledge search failed: {e}")

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

        # 3. 拼装 Prompt
        prompt = GENERATE_QUIZ_PROMPT.format(
            question_count=inputs.get("question_count", 5),
            question_types=inputs.get("question_types", "选择题"),
            difficulty=inputs.get("difficulty", "中等"),
            topic=topic,
            key_points=key_points_text or "无",
            knowledge_context=knowledge_context or "无参考资料，请基于常识出题。",
        )

        # 4. 调用 LLM 生成题目
        raw_response = await self.call_llm(runtime, prompt)
        response_text = self._coerce_text(raw_response)
        questions = self._parse_questions(response_text)

        quiz_session_id = f"quiz__{datetime.now().strftime('%Y%m%d__%H%M%S')}"

        # 5. 返回结果
        return AgentResult(
            state_update={
                "questions": questions,
                "quiz_session_id": quiz_session_id,
                "quiz_metadata": {
                    "question_count": len(questions),
                    "topic": topic,
                    "question_types": inputs.get("question_types", "选择题"),
                },
            },
            messages=[{"role": "assistant", "content": f"已生成 {len(questions)} 道题目。"}],
            artifacts=[
                Artifact(
                    type="quiz_questions",
                    name=quiz_session_id,
                    content=questions,
                    format="json",
                ),
            ],
        )

    def _parse_questions(self, text: str) -> list[dict]:
        """从 LLM 返回文本中提取 JSON 题目列表。"""
        # 尝试提取 JSON 数组
        text = text.strip()

        # 如果被 markdown 代码块包裹，先解包
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

        # 尝试直接解析 JSON
        try:
            questions = json.loads(text)
            if isinstance(questions, list):
                return questions
        except json.JSONDecodeError:
            pass

        # 尝试查找 JSON 数组的起始位置
        try:
            idx = text.index("[")
            end_idx = text.rindex("]") + 1
            questions = json.loads(text[idx:end_idx])
            if isinstance(questions, list):
                return questions
        except (ValueError, json.JSONDecodeError):
            pass

        # 解析失败，返回空列表
        print(f"[QuizAgent] Failed to parse questions from LLM response: {text[:200]}")
        return []

    def _coerce_text(self, response: Any) -> str:
        """将 LLM 响应统一转为文本。"""
        if response is None:
            return ""
        if hasattr(response, "choices") and response.choices:
            return response.choices[0].message.content or ""
        return str(response)
