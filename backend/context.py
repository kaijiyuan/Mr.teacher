COMPRESSION_THRESHOLD = 10
KEEP_WINDOW = 6
MAX_CONTEXT_MESSAGES = 20


def manage_memory(messages: list, llm_service) -> dict:
    """Compress older conversation messages into a short summary when needed."""
    if len(messages) <= COMPRESSION_THRESHOLD:
        return {"summary": "", "compressed": False}

    to_compress = messages[:-KEEP_WINDOW]
    compress_prompt = _build_compress_prompt(to_compress)

    try:
        response = llm_service.create_summary(
            [{"role": "user", "content": compress_prompt}],
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        return {"summary": summary, "compressed": True}
    except Exception as e:
        print(f"[Context] Memory compression failed: {e}")
        return {"summary": "", "compressed": False}


def build_context(messages: list, summary: str = "") -> list:
    """Build the context messages sent to the LLM."""
    ctx = []

    if summary:
        ctx.append({
            "role": "system",
            "content": f"以下是之前的对话摘要，请基于这个上下文继续对话：\n{summary}",
        })

    recent = messages[-MAX_CONTEXT_MESSAGES:]
    for msg in recent:
        role = msg.get("role", "user") if isinstance(msg, dict) else "user"
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        ctx.append({"role": role, "content": content})

    return ctx


def _build_compress_prompt(messages: list) -> str:
    history_text = ""
    for msg in messages:
        role = msg.get("role", "user") if isinstance(msg, dict) else "user"
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        history_text += f"[{role}]: {content}\n"

    return f"""请总结以下对话的核心内容，保留关键信息（用户的问题、AI 的主要回答、讨论的主题）。
要求：
- 用中文简洁总结
- 保留关键知识点
- 控制在 200 字以内

对话内容：
{history_text}

总结："""
