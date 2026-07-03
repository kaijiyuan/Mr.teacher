"""Prompts for the file parser agent."""

SUMMARY_PROMPT_TEMPLATE = """你是一个文档摘要助手。请根据以下文档全文内容，生成一份简洁的中文摘要。

要求：
1. 摘要长度控制在 200-300 字。
2. 概括文档的核心主题和关键内容。
3. 如果文档包含技术概念，列出 3-5 个核心知识点。
4. 如果文档有章节结构，简要说明各章节内容。

请直接输出摘要，不要添加额外说明。

文档内容：
{document_text}
"""


def build_summary_prompt(document_text: str) -> str:
    """Build the summary prompt with the full document text.

    To avoid excessive token usage, truncate very long texts.
    """
    max_chars = 8000
    truncated = document_text[:max_chars]
    if len(document_text) > max_chars:
        truncated += "\n\n[文档内容过长，已截断，仅展示前 {} 字]".format(max_chars)
    return SUMMARY_PROMPT_TEMPLATE.format(document_text=truncated)
