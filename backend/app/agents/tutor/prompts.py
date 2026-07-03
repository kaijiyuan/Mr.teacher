from __future__ import annotations
from typing import Any


PROFILE_LABELS = {
    "topic": "学习主题",
    "knowledge_level": "当前基础",
    "learning_goal": "学习目标",
    "time_available": "可投入时间",
    "learning_style": "学习偏好",
    "scenario": "使用场景",
    "constraints": "限制条件",
    "source_scope": "资料范围",
}


def format_profile(user_profile: dict[str, Any]) -> str:
    if not user_profile:
        return "暂无用户画像，请先基于用户当前问题进行温和引导。"

    lines = []
    for key, label in PROFILE_LABELS.items():
        value = user_profile.get(key)
        if isinstance(value, list):
            value = "、".join(str(item) for item in value if item)
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines) if lines else "暂无有效用户画像。"


def format_history(conversation_history: list[dict[str, Any]] | None, max_turns: int = 6) -> str:
    if not conversation_history:
        return "暂无历史对话。"

    recent_turns = conversation_history[-max_turns:]
    lines = []
    for turn in recent_turns:
        role = turn.get("role", "unknown")
        content = str(turn.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "暂无有效历史对话。"


def build_guidance_prompt(
    *,
    teaching_style: str,
    instruction: str,
    user_message: str,
    user_profile: dict[str, Any],
    knowledge_context: str,
    conversation_history: list[dict[str, Any]] | None,
) -> str:
    context = knowledge_context.strip() if knowledge_context else "暂无外部知识库内容。"

    return f"""你是一个中文学习助手，当前采用「{teaching_style}」。

你的任务：
1. 结合用户画像、历史对话和资料上下文回答。
2. 保持引导式教学，不要一次性展开过多无关内容。
3. 如果资料上下文不足，明确说明不确定点，并基于通用知识给出下一步学习路径。
4. 回答后给出一个自然的追问或下一步学习动作。

用户画像：
{format_profile(user_profile)}

最近对话：
{format_history(conversation_history)}

资料上下文：
{context}

用户当前问题：
{user_message}

教学策略要求：
{instruction}

请用中文回答。"""
