from __future__ import annotations

GENERATE_QUIZ_PROMPT = """你是一个学习出题助手。请根据以下资料生成 {question_count} 道题目。

题目类型要求：{question_types}

要求：
1. 题目必须基于资料内容，不能编造
2. 必须包含答案和解析
3. 标注每道题对应的知识点
4. 难度：{difficulty}
5. 返回格式为 JSON 数组，每道题的结构如下：
{{
    "id": "q_1",
    "type": "single_choice",
    "stem": "题干",
    "options": [
        {{"id": "A", "text": "选项A"}},
        {{"id": "B", "text": "选项B"}},
        {{"id": "C", "text": "选项C"}},
        {{"id": "D", "text": "选项D"}}
    ],
    "answer": "A",
    "explanation": "解析：为什么选这个答案",
    "knowledge_point": "所属知识点名称",
    "difficulty": 2,
    "source": {{"document_id": "来源文档ID（如果有）", "chunk_id": "来源内容块ID（如果有）"}}
}}

不同类型题目的结构差异：
- single_choice / multiple_choice：需要 options 字段
- true_false：options 为 [{{"id": "A", "text": "正确"}}, {{"id": "B", "text": "错误"}}]
- fill_blank：不需要 options，answer 直接填答案文本

学习主题：{topic}

核心知识点：
{key_points}

参考资料：
{knowledge_context}

请直接输出 JSON 数组，不要添加其他内容。"""


EVALUATE_PROMPT = """你是一个答题评估助手。请批改以下答题记录，并给出评估结果。

答题记录：
{questions_with_answers}

要求：
1. 逐题判断对错
2. 汇总薄弱知识点（答错的题涉及的知识点）
3. 给出有针对性的复习建议
4. 返回格式为 JSON，结构如下：
{{
    "score": 80,
    "correct_count": 4,
    "total_count": 5,
    "weak_points": ["薄弱知识点1", "薄弱知识点2"],
    "suggestions": ["复习建议1", "复习建议2"]
}}

请直接输出 JSON，不要添加其他内容。"""
