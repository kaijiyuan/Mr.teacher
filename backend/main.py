from __future__ import annotations
import json
from typing import Any, AsyncGenerator, Optional

import base64

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.agents.file_parser.agent import FileParserAgent
from app.services.container import services
from context import build_context, manage_memory
from memory import (
    delete_session,
    list_sessions,
    load_session_messages,
    load_session_profile,
    load_session_summary,
    new_session_id,
    save_session,
)

app = FastAPI(title="AI Chat MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_profile: Optional[dict[str, Any]] = None


def _event_line(event: str, data: dict) -> str:
    return json.dumps({"event": event, "data": data}, ensure_ascii=False) + "\n"


@app.get("/")
async def root():
    return {"message": "AI Chat MVP Running"}


@app.get("/api/v1/sessions")
async def get_sessions():
    sessions = list_sessions()
    return {"sessions": sessions}


@app.delete("/api/v1/sessions/{session_id}")
async def remove_session(session_id: str):
    delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/v1/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    messages = load_session_messages(session_id)
    profile = load_session_profile(session_id)
    return {"session_id": session_id, "messages": messages, "user_profile": profile}


@app.get("/api/v1/profile")
async def get_profile():
    """Return the most recent session's user profile (the learning portrait)."""
    sessions = list_sessions()
    if sessions:
        latest = sessions[0]
        profile = latest.get("profile", {})
        if profile:
            return {"profile": profile, "session_id": latest["session_id"]}
    return {"profile": {}, "session_id": ""}


@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    async def _generate() -> AsyncGenerator[str, None]:
        session_id = request.session_id or new_session_id()
        yield _event_line("start", {"session_id": session_id})

        messages = load_session_messages(session_id)
        summary = load_session_summary(session_id)
        user_profile = request.user_profile or load_session_profile(session_id)

        messages.append({"role": "user", "content": request.message})
        context = build_context(messages, summary)
        profile_message = services.profile.build_system_message(user_profile)

        # ── RAG: search all knowledge bases for relevant chunks ──────
        knowledge_context = ""
        docs = services.knowledge.list_documents()
        if docs:
            all_chunks: list[dict] = []
            for doc in docs:
                kb_id = doc.get("knowledge_base_id", "")
                try:
                    results = await services.knowledge.search(
                        knowledge_base_id=kb_id,
                        query=request.message,
                        top_k=3,
                        mode="hybrid",
                    )
                    for r in results:
                        r["_source_file"] = doc.get("file_name", "")
                    all_chunks.extend(results)
                except Exception:
                    pass

            # Merge, deduplicate, and pick top chunks across all KBs
            all_chunks.sort(key=lambda c: c.get("score", 0), reverse=True)
            seen: set[str] = set()
            top_chunks: list[dict] = []
            for c in all_chunks:
                cid = c.get("chunk_id", "")
                if cid not in seen:
                    seen.add(cid)
                    top_chunks.append(c)
                if len(top_chunks) >= 5:
                    break

            if top_chunks:
                parts = ["以下是从已上传资料中检索到的相关内容："]
                for i, c in enumerate(top_chunks, 1):
                    src = c.get("_source_file", "未知")
                    page = c.get("page", "?")
                    parts.append(f"[资料{i}] 来源：{src} 第{page}页\n{c['text']}")
                knowledge_context = "\n\n".join(parts)

        # Build final context
        if profile_message:
            context = [profile_message, *context]
        if knowledge_context:
            context.insert(0, {
                "role": "system",
                "content": f"请结合以下资料回答问题。如果资料不足以回答，请基于你的知识补充并说明。\n\n{knowledge_context}",
            })

        try:
            stream = services.llm.stream_chat(context)

            collected_content = ""
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    collected_content += delta.content
                    yield _event_line("delta", {"text": delta.content})

            messages.append({"role": "assistant", "content": collected_content})

            result = manage_memory(messages, services.llm)
            new_summary = result.get("summary", "") or summary

            save_session(
                session_id,
                messages,
                summary=new_summary,
                user_profile=services.profile.normalize(user_profile),
            )

            yield _event_line(
                "done",
                {
                    "session_id": session_id,
                    "message_count": len(messages),
                },
            )

        except Exception as e:
            yield _event_line("error", {"message": str(e)})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Knowledge / PDF upload ──────────────────────────────────────────

@app.get("/api/v1/knowledge/documents")
async def list_documents():
    """List all uploaded documents."""
    docs = services.knowledge.list_documents()
    return {"documents": docs}


@app.post("/api/v1/knowledge/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF, parse it via MinerU, and store into the knowledge base."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="只支持 PDF 文件")

    if services.mineru is None:
        raise HTTPException(
            503,
            detail="MinerU PDF 解析服务未配置。请在 backend/.env 中设置 MINERU_API_KEY。"
            "获取地址: https://mineru.net",
        )

    try:
        raw = await file.read()
        encoded = base64.b64encode(raw).decode()
    except Exception:
        raise HTTPException(400, detail="文件读取失败")

    runtime = services.to_runtime()
    agent = FileParserAgent()

    try:
        result = await agent.run(
            {
                "file_content": encoded,
                "file_name": file.filename,
                "user_profile": {},
            },
            runtime,
        )
    except Exception as exc:
        raise HTTPException(500, detail=f"解析过程异常: {exc}")

    if result.error is not None:
        raise HTTPException(500, detail=f"解析失败: {result.error.message}")

    return {
        "status": "ok",
        **result.state_update,
        "artifacts": [
            {"type": a.type, "name": a.name, "format": a.format}
            for a in result.artifacts
        ],
    }


@app.get("/api/v1/knowledge/documents/{document_id}")
async def get_document(document_id: str):
    """Get document details and index stats."""
    doc = await services.knowledge.get_document(document_id)
    if doc is None:
        raise HTTPException(404, detail="文档不存在")
    kb_id = doc.get("knowledge_base_id", "")
    stats = services.knowledge.index_stats(kb_id)
    graph_stats = services.entity_graph.graph_stats(kb_id)
    return {
        "document": doc,
        "index_stats": stats,
        "graph_stats": graph_stats,
    }


# ── Mindmap ────────────────────────────────────────────────────────

@app.post("/api/v1/knowledge/documents/{document_id}/mindmap")
async def generate_mindmap(document_id: str):
    """Force regenerate a mindmap (ignores cache)."""
    doc = await services.knowledge.get_document(document_id)
    if doc is None:
        raise HTTPException(404, detail="文档不存在")

    from app.agents.mindmap.agent import MindmapAgent

    runtime = services.to_runtime()
    agent = MindmapAgent()
    result = await agent.run(
        {"document_id": document_id,
         "knowledge_base_id": doc.get("knowledge_base_id", ""),
         "document_summary": "", "user_profile": {}}, runtime)

    if result.error is not None:
        raise HTTPException(500, detail=f"生成失败: {result.error.message}")

    # Always update cache
    services.knowledge.save_mindmap(document_id, result.state_update)
    return {"document_id": document_id, **result.state_update, "cached": False}


@app.get("/api/v1/knowledge/documents/{document_id}/mindmap")
async def get_mindmap(document_id: str):
    """Get a cached mindmap, or generate + cache on first access."""
    doc = await services.knowledge.get_document(document_id)
    if doc is None:
        raise HTTPException(404, detail="文档不存在")

    # Return cached if exists
    cached = services.knowledge.load_mindmap(document_id)
    if cached is not None:
        return {"document_id": document_id, "mindmap": cached["mindmap"],
                "key_points": cached.get("key_points", []), "cached": True}

    # Generate
    from app.agents.mindmap.agent import MindmapAgent

    runtime = services.to_runtime()
    agent = MindmapAgent()
    result = await agent.run(
        {"document_id": document_id,
         "knowledge_base_id": doc.get("knowledge_base_id", ""),
         "document_summary": "", "user_profile": {}}, runtime)

    if result.error is not None:
        raise HTTPException(500, detail=f"生成失败: {result.error.message}")

    # Cache
    services.knowledge.save_mindmap(document_id, result.state_update)
    return {"document_id": document_id, **result.state_update, "cached": False}


@app.delete("/api/v1/knowledge/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document, its chunks, and rebuild the affected indexes."""
    try:
        result = await services.knowledge.delete_document(document_id)
    except KeyError:
        raise HTTPException(404, detail="文档不存在")

    # Also clean up entity graph if present
    kb_id = result.get("knowledge_base_id", "")
    if kb_id:
        path = services.entity_graph._graph_path(kb_id)
        if path.exists():
            path.unlink()

    return {"status": "deleted", **result}


# ── PPT download ──────────────────────────────────────────────────────

import os as _os

from app.agents.ppt.agent import PPTAgent
from app.agents.quiz.agent import QuizAgent
from app.agents.quiz.evaluator import evaluate_simple
from app.services.quiz_session import save_quiz_session, load_quiz_session, list_quiz_sessions, delete_quiz_session, new_session_id as new_quiz_session_id
from app.services.ppt_session import save_ppt_session, load_ppt_session, list_ppt_sessions, delete_ppt_session, new_session_id as new_ppt_session_id

PPT_DATA_DIR = _os.path.join(_os.path.dirname(__file__), "data", "ppt")


@app.get("/api/v1/ppt/{artifact_id}/download")
async def download_ppt(artifact_id: str):
    """Download a generated PPT file by its artifact ID (newest match)."""
    ppt_dir = PPT_DATA_DIR
    if not _os.path.isdir(ppt_dir):
        raise HTTPException(404, detail="PPT 目录不存在")

    # Always pick the newest file matching the artifact_id
    candidates = [
        f for f in _os.listdir(ppt_dir)
        if f.startswith(artifact_id) and f.endswith(".pptx")
    ]
    if not candidates:
        raise HTTPException(404, detail=f"PPT 文件不存在: {artifact_id}")

    # Sort by modification time (newest first)
    candidates.sort(
        key=lambda f: _os.path.getmtime(_os.path.join(ppt_dir, f)),
        reverse=True,
    )
    fname = candidates[0]
    file_path = _os.path.join(ppt_dir, fname)
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=fname,
    )


@app.get("/api/v1/ppt/file/{file_name}/download")
async def download_ppt_by_name(file_name: str):
    """Download a specific PPT file by exact filename."""
    ppt_dir = PPT_DATA_DIR
    if not _os.path.isdir(ppt_dir):
        raise HTTPException(404, detail="PPT 目录不存在")

    # Sanitize: only allow .pptx files, prevent path traversal
    safe_name = _os.path.basename(file_name)
    if not safe_name.endswith(".pptx"):
        raise HTTPException(400, detail="无效的文件名")

    file_path = _os.path.join(ppt_dir, safe_name)
    if not _os.path.isfile(file_path):
        raise HTTPException(404, detail=f"PPT 文件不存在: {safe_name}")

    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe_name,
    )


def _load_latest_profile() -> dict:
    """Load the learning portrait from the most recent chat session."""
    try:
        sessions = list_sessions()
        if sessions:
            return sessions[0].get("profile", {})
    except Exception:
        pass
    return {}


class PptGenerateRequest(BaseModel):
    topic: str = ""
    slide_count: int = 10
    knowledge_base_id: str = ""
    key_points: list[dict] = []
    quiz_evaluation: dict = {}
    user_profile: dict = {}


@app.post("/api/v1/ppt/generate")
async def generate_ppt(req: PptGenerateRequest):
    """Generate a PPT outline and .pptx file."""
    runtime = services.to_runtime()
    agent = PPTAgent()
    result = await agent.run(
        {
            "topic": req.topic,
            "slide_count": req.slide_count,
            "knowledge_base_id": req.knowledge_base_id,
            "key_points": req.key_points,
            "quiz_evaluation": req.quiz_evaluation,
            "user_profile": req.user_profile,
        },
        runtime,
    )

    if result.error is not None:
        raise HTTPException(500, detail=f"PPT 生成失败: {result.error.message}")

    ppt_artifact_id = result.state_update.get("ppt_artifact_id", "")
    ppt_outline = result.state_update.get("ppt_outline", {})
    ppt_file_path = result.state_update.get("ppt_file_path", "")
    ppt_file_name = _os.path.basename(ppt_file_path) if ppt_file_path else ""

    # Auto-save session
    session_id = new_ppt_session_id()
    save_ppt_session(
        session_id=session_id,
        topic=req.topic,
        slide_count=req.slide_count,
        ppt_outline=ppt_outline,
        ppt_file_path=ppt_file_path,
        ppt_artifact_id=ppt_artifact_id,
    )

    return {
        "session_id": session_id,
        "ppt_artifact_id": ppt_artifact_id,
        "ppt_outline": ppt_outline,
        "ppt_file_path": ppt_file_path,
        "ppt_file_name": ppt_file_name,
    }


# ── PPT session CRUD ─────────────────────────────────────────────────


@app.get("/api/v1/ppt/sessions")
async def get_ppt_sessions():
    """List all PPT sessions."""
    sessions = list_ppt_sessions()
    return {"sessions": sessions}


@app.get("/api/v1/ppt/sessions/{session_id}")
async def get_ppt_session(session_id: str):
    """Load a specific PPT session."""
    data = load_ppt_session(session_id)
    if data is None:
        raise HTTPException(404, detail="PPT 会话不存在")
    return data


@app.delete("/api/v1/ppt/sessions/{session_id}")
async def remove_ppt_session(session_id: str):
    """Delete a PPT session."""
    delete_ppt_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ── Study Plan ────────────────────────────────────────────────────────

GENERATE_PLAN_PROMPT = """你是一个学习规划助手。请根据以下学习画像和资料内容，生成一份详细的学习时间计划表。

学习画像：
- 学习主题：{topic}
- 学习目标：{goal}
- 当前水平：{level}
- 每天可用时间：{daily_time} 小时

薄弱知识点（需重点复习）：
{weak_points}

参考资料摘要：
{knowledge_summary}

要求：
1. 将学习内容按天规划，生成 3-7 天的学习计划
2. 每天包含：日期、学习主题、具体学习内容、预计时长、学习目标
3. 优先安排薄弱知识点
4. 最后一天安排综合复习和练习
5. 返回 JSON 数组，结构如下：
{{
    "day": 1,
    "date_label": "第1天",
    "topic": "当天学习主题",
    "duration": "2小时",
    "content": ["具体学习内容1", "具体学习内容2"],
    "goal": "当天学习目标",
    "type": "学习" 或 "练习" 或 "复习" 或 "综合"
}}

请直接输出 JSON 数组，不要添加其他内容。"""


class PlanGenerateRequest(BaseModel):
    topic: str = ""
    goal: str = ""
    level: str = ""
    daily_time: float = 0.0


@app.post("/api/v1/plan/generate")
async def generate_plan(req: PlanGenerateRequest):
    """Generate a study plan based on user profile and knowledge base content.
    
    Auto-loads the learning portrait from the most recent chat session
    if topic/goal/level are not provided.
    """
    # 0. Auto-load profile from latest chat session
    topic = req.topic
    goal = req.goal
    level = req.level
    daily_time = req.daily_time

    if not topic:
        try:
            _sessions = list_sessions()
            if _sessions:
                _p = _sessions[0].get("profile", {})
                if _p and _p.get("topic"):
                    topic = _p.get("topic", "")
                    level = level or _p.get("knowledge_level", "初学者")
                    goal = goal or _p.get("learning_goal", "系统学习并掌握核心知识")
                    time_str = _p.get("time_available", "")
                    if not daily_time and "分钟" in time_str:
                        import re as _re
                        nums = _re.findall(r"\d+", time_str)
                        if nums:
                            daily_time = float(nums[0]) / 60
                    if not daily_time:
                        daily_time = 2.0
        except Exception:
            pass
        if not topic:
            from fastapi import HTTPException
            raise HTTPException(400, detail="请提供学习主题，或在对话页面先设置学习画像")

    # Defaults
    goal = goal or "系统学习并掌握核心知识"
    level = level or "初学者"
    daily_time = daily_time or 2.0

    # 1. Search knowledge base for relevant content
    knowledge_summary = ""
    docs = services.knowledge.list_documents()
    if docs:
        parts = []
        for doc in docs[:3]:
            kb_id = doc.get("knowledge_base_id", "")
            try:
                results = await services.knowledge.search(
                    knowledge_base_id=kb_id,
                    query=topic,
                    top_k=3,
                    mode="hybrid",
                )
                for r in results:
                    text = r.get("text", "")
                    if text:
                        parts.append(text[:300])
            except Exception:
                pass
        if parts:
            knowledge_summary = "\n".join(parts)

    # 2. Collect weak points from quiz history
    weak_points = []
    quiz_sessions = list_quiz_sessions()
    for s in quiz_sessions[:5]:
        data = load_quiz_session(s["session_id"])
        if data and data.get("evaluation"):
            wp = data["evaluation"].get("weak_points", [])
            weak_points.extend(wp)
    weak_points = list(set(weak_points))[:5]

    # 3. Generate plan via LLM
    prompt = GENERATE_PLAN_PROMPT.format(
        topic=topic,
        goal=goal,
        level=level,
        daily_time=daily_time,
        weak_points="、".join(weak_points) if weak_points else "暂无",
        knowledge_summary=knowledge_summary[:2000] or "暂无参考资料，请基于常识规划。",
    )

    llm = services.llm
    response = llm.client.chat.completions.create(
        model=llm.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        stream=False,
    )
    text = response.choices[0].message.content.strip()

    # 4. Parse response
    import json
    try:
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
        plan = json.loads(text) if text.startswith("[") else []
    except (json.JSONDecodeError, ValueError):
        plan = []

    return {
        "plan": plan,
        "summary": {
            "topic": topic,
            "goal": goal,
            "level": level,
            "daily_time": daily_time,
            "total_days": len(plan),
            "weak_points": weak_points,
        },
    }


# ── Quiz ──────────────────────────────────────────────────────────────

class QuizGenerateRequest(BaseModel):
    topic: str = ""
    question_count: int = 5
    question_types: str = "选择题"
    difficulty: str = "中等"
    session_id: str = ""


@app.post("/api/v1/quiz/generate")
async def generate_quiz(req: QuizGenerateRequest):
    """Generate quiz questions using QuizAgent.
    
    Automatically searches all uploaded knowledge bases for context.
    Auto-saves the generated questions as a quiz session.
    """
    runtime = services.to_runtime()
    agent = QuizAgent()

    # Auto-collect knowledge_base_ids from all uploaded docs
    docs = services.knowledge.list_documents()
    kb_ids = list({d.get("knowledge_base_id", "") for d in docs if d.get("knowledge_base_id")})

    # Generate questions for each KB and merge
    all_questions = []
    for kb_id in kb_ids:
        result = await agent.run(
            {
                "knowledge_base_id": kb_id,
                "topic": req.topic,
                "question_count": req.question_count // max(len(kb_ids), 1),
                "question_types": req.question_types,
                "difficulty": req.difficulty,
                "user_profile": {},
                "key_points": [],
            },
            runtime,
        )
        if result.error is None:
            all_questions.extend(result.state_update.get("questions", []))

    # Fallback: generate without KB if no docs
    if not kb_ids:
        result = await agent.run(
            {
                "knowledge_base_id": "",
                "topic": req.topic,
                "question_count": req.question_count,
                "question_types": req.question_types,
                "difficulty": req.difficulty,
                "user_profile": {},
                "key_points": [],
            },
            runtime,
        )
        if result.error is None:
            all_questions = result.state_update.get("questions", [])

    # Limit to requested count
    all_questions = all_questions[:req.question_count]

    # Reuse or create session_id
    session_id = req.session_id or new_quiz_session_id()

    # Auto-save the generated session
    save_quiz_session(
        session_id=session_id,
        topic=req.topic,
        questions=all_questions,
        status="in_progress",
    )

    return {
        "questions": all_questions,
        "question_count": len(all_questions),
        "session_id": session_id,
    }


class QuizEvaluateRequest(BaseModel):
    questions: list[dict] = []
    user_answers: dict[str, str] = {}
    session_id: str = ""


@app.post("/api/v1/quiz/evaluate")
async def evaluate_quiz(req: QuizEvaluateRequest):
    """Evaluate user answers against correct answers.
    Auto-saves the completed evaluation.
    """
    evaluation = evaluate_simple(req.questions, req.user_answers)
    eval_dict = {
        "score": evaluation.score,
        "correct_count": evaluation.correct_count,
        "total_count": evaluation.total_count,
        "weak_points": evaluation.weak_points,
        "suggestions": evaluation.suggestions,
        "details": evaluation.details,
    }

    # Auto-save completed session
    if req.session_id:
        save_quiz_session(
            session_id=req.session_id,
            topic="",
            questions=req.questions,
            user_answers=req.user_answers,
            evaluation=eval_dict,
            status="completed",
        )

    return eval_dict


# ── Quiz session CRUD ────────────────────────────────────────────────


@app.get("/api/v1/quiz/sessions")
async def get_quiz_sessions():
    """List all quiz sessions."""
    sessions = list_quiz_sessions()
    return {"sessions": sessions}


@app.get("/api/v1/quiz/sessions/{session_id}")
async def get_quiz_session(session_id: str):
    """Load a specific quiz session."""
    data = load_quiz_session(session_id)
    if data is None:
        raise HTTPException(404, detail="出题会话不存在")
    return data


@app.delete("/api/v1/quiz/sessions/{session_id}")
async def remove_quiz_session(session_id: str):
    """Delete a quiz session."""
    delete_quiz_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.post("/api/v1/quiz/sessions/{session_id}/save")
async def save_quiz_session_api(session_id: str, data: dict):
    """Save in-progress quiz answers for a session."""
    topic = data.get("topic", "")
    questions = data.get("questions", [])
    user_answers = data.get("user_answers", {})
    save_quiz_session(
        session_id=session_id,
        topic=topic,
        questions=questions,
        user_answers=user_answers,
        status="in_progress",
    )
    return {"status": "saved", "session_id": session_id}
