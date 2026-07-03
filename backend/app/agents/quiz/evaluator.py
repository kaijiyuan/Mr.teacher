from __future__ import annotations

import json
from typing import Any

from app.agents.quiz.models import QuizEvaluation


def evaluate_simple(
    questions: list[dict],
    user_answers: dict[str, str],
) -> QuizEvaluation:
    """纯逻辑批改：逐题对比答案，无需 LLM。

    Args:
        questions: 题目列表，每题需包含 id, answer, knowledge_point 字段。
        user_answers: {question_id: user_answer_text}。

    Returns:
        QuizEvaluation 评估结果。
    """
    total = len(questions)
    if total == 0:
        return QuizEvaluation()

    correct = 0
    weak_set: set[str] = set()
    details: list[dict] = []

    for q in questions:
        qid = q.get("id", "")
        correct_answer = q.get("answer", "")
        user_answer = user_answers.get(qid, "")
        is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
        if is_correct:
            correct += 1
        else:
            kp = q.get("knowledge_point", "")
            if kp:
                weak_set.add(kp)

        details.append({
            "question_id": qid,
            "correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "knowledge_point": q.get("knowledge_point", ""),
        })

    score = round(correct / total * 100, 1)
    suggestions = _generate_suggestions(weak_set)

    return QuizEvaluation(
        score=score,
        correct_count=correct,
        total_count=total,
        weak_points=sorted(weak_set),
        suggestions=suggestions,
        details=details,
    )


async def evaluate_with_llm(
    questions: list[dict],
    user_answers: dict[str, str],
    llm_service: Any,
) -> QuizEvaluation:
    """LLM 辅助批改：对开放题或复杂题调用 LLM 评估。"""
    if not questions:
        return QuizEvaluation()

    from app.agents.quiz.prompts import EVALUATE_PROMPT

    # 构建答题记录文本
    records = []
    for q in questions:
        qid = q.get("id", "")
        records.append(
            f"题目 {qid}（{q.get('type', '')}）：{q.get('stem', '')}\n"
            f"正确答案：{q.get('answer', '')}\n"
            f"用户答案：{user_answers.get(qid, '未作答')}\n"
            f"知识点：{q.get('knowledge_point', '')}\n"
        )

    prompt = EVALUATE_PROMPT.format(
        questions_with_answers="\n".join(records),
    )

    response = llm_service.client.chat.completions.create(
        model=llm_service.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        stream=False,
    )

    text = response.choices[0].message.content.strip()

    # 解析返回的 JSON
    try:
        # 去掉可能的 markdown 代码块
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

        data = json.loads(text)
        return QuizEvaluation(
            score=data.get("score", 0.0),
            correct_count=data.get("correct_count", 0),
            total_count=data.get("total_count", len(questions)),
            weak_points=data.get("weak_points", []),
            suggestions=data.get("suggestions", []),
        )
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[QuizEvaluator] Failed to parse LLM evaluation: {e}")
        # 降级到简单批改
        return evaluate_simple(questions, user_answers)


def _generate_suggestions(weak_points: set[str]) -> list[str]:
    """根据薄弱知识点生成复习建议。"""
    if not weak_points:
        return ["掌握情况良好！继续保持。"]

    suggestions = []
    kp_list = sorted(weak_points)

    if len(kp_list) <= 2:
        suggestions.append(f"建议重点复习：{'、'.join(kp_list)}")
    else:
        suggestions.append(f"薄弱知识点较多（{len(kp_list)} 个），建议系统复习以下内容：")
        for kp in kp_list:
            suggestions.append(f"- {kp}")
        suggestions.append("可以通过重新学习相关章节、多做练习来巩固。")

    return suggestions
