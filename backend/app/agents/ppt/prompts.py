from __future__ import annotations

GENERATE_PPT_OUTLINE_PROMPT = """你是一个学习复习材料制作助手。请根据以下资料生成一份 PPT 复习大纲。

要求：
1. 大纲应覆盖所有核心知识点
2. 每张幻灯片包含标题、要点列表和讲稿提示
3. 结构合理，先概念后细节，循序渐进
4. 如果提供了答题评估结果，优先突出薄弱知识点
5. 返回格式为 JSON 数组，结构如下：
{{
    "title": "幻灯片标题",
    "bullets": ["要点1", "要点2", "要点3"],
    "speaker_notes": "讲稿或复习提示文本",
    "source_chunks": ["chunk_1", "chunk_2"]
}}

学习主题：{topic}
最多不超过 {slide_count} 张幻灯片

核心知识点：
{key_points}

参考资料：
{knowledge_context}

薄弱知识点（需重点复习）：
{weak_points}

请直接输出 JSON 数组，不要添加其他内容。"""


GENERATE_PPT_SUMMARY_PROMPT = """你是一个学习复习材料制作助手。请根据以下 PPT 大纲生成一段整体摘要（2-3 句话），描述这份复习 PPT 的内容和目的。

PPT 标题：{title}
PPT 大纲：
{outline}

请直接输出摘要文本，不要添加其他内容。"""
