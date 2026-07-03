"""Prompt templates for mindmap generation."""

MINDMAP_SYSTEM = """你是一个知识结构专家。请根据提供的文档内容，生成一个层次化的思维导图。

要求：
1. 最外层为文档主题（1个根节点）
2. 第二层为核心章节/概念（3-8个）
3. 第三层为每个概念下的关键子点（1-5个）
4. 每个节点包含：标题、一句话摘要
5. 同时提取 5-10 个核心知识点

输出格式（严格 JSON）：
{
  "title": "文档主题",
  "nodes": [
    {
      "id": "n1",
      "title": "核心概念名称",
      "summary": "一句话解释该概念",
      "importance": 5,
      "children": [
        {
          "id": "n1_1",
          "title": "子概念",
          "summary": "解释",
          "importance": 3,
          "children": []
        }
      ]
    }
  ],
  "key_points": [
    {
      "title": "知识点名称",
      "description": "知识点详细说明",
      "difficulty": 3
    }
  ]
}

注意：importance 为 1-5，5 最重要。difficulty 为 1-5，5 最难。"""


def build_mindmap_prompt(
    *,
    document_summary: str = "",
    knowledge_context: str,
) -> str:
    """Build the full mindmap generation prompt."""
    parts = ["请根据以下文档内容生成思维导图。"]
    if document_summary:
        parts.append(f"文档概要：{document_summary}")
    parts.append(f"文档内容片段：\n{knowledge_context}")
    parts.append("请直接输出 JSON，不要添加其他内容。")
    return "\n\n".join(parts)
