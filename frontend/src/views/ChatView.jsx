import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, History, Loader2, Plus, RefreshCcw, Send } from "lucide-react";

import { API_BASE, api } from "../api.js";
import { Markdown } from "../components/Markdown.jsx";
import { PdfUpload, DocChip } from "../components/PdfUpload.jsx";
import { PROFILE_DEFAULTS, ProfileSetup } from "../components/ProfileSetup.jsx";

export function ChatView({ hidden, onNotice }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [sessions, setSessions] = useState([]);
  const [showSessionList, setShowSessionList] = useState(false);
  const [profileDraft, setProfileDraft] = useState(PROFILE_DEFAULTS);
  const [userProfile, setUserProfile] = useState(null);
  const [profileReady, setProfileReady] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [showUpload, setShowUpload] = useState(false);
  const scrollRef = useRef(null);
  const initialSessionLoadedRef = useRef(false);

  const switchSession = useCallback(async (sid) => {
    setSessionId(sid);
    setShowSessionList(false);
    try {
      const data = await api(`/api/v1/sessions/${encodeURIComponent(sid)}/messages`);
      const nextProfile = data.user_profile || null;
      setMessages(data.messages || []);
      setUserProfile(nextProfile);
      setProfileDraft({ ...PROFILE_DEFAULTS, ...(nextProfile || {}) });
      setProfileReady(true);
    } catch {
      setMessages([]);
      setUserProfile(null);
      setProfileDraft(PROFILE_DEFAULTS);
      setProfileReady(true);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const data = await api("/api/v1/sessions");
      const nextSessions = data.sessions || [];
      setSessions(nextSessions);
      if (!initialSessionLoadedRef.current) {
        initialSessionLoadedRef.current = true;
        if (nextSessions.length) {
          await switchSession(nextSessions[0].session_id);
        }
      }
    } catch {
      // ignore
    }
  }, [switchSession]);

  const newSession = useCallback(() => {
    setSessionId("");
    setMessages([]);
    setUserProfile(null);
    setProfileDraft(PROFILE_DEFAULTS);
    setProfileReady(false);
    setShowSessionList(false);
  }, []);

  const loadDocs = useCallback(async () => {
    try {
      const data = await api("/api/v1/knowledge/documents");
      setUploadedDocs(data.documents || []);
    } catch { /* ignore */ }
  }, []);

  const handleDocUploaded = useCallback((doc) => {
    setUploadedDocs((prev) => [doc, ...prev]);
    onNotice(`知识库已更新：${doc.document_metadata?.page_count ?? "?"} 页，${doc.document_metadata?.chunk_count ?? "?"} 个内容块`);
  }, [onNotice]);

  const handleRemoveDoc = useCallback(async (documentId) => {
    try {
      await api(`/api/v1/knowledge/documents/${encodeURIComponent(documentId)}`, {
        method: "DELETE",
      });
      setUploadedDocs((prev) => prev.filter((d) => d.document_id !== documentId));
      onNotice("文档已删除，索引已重建。");
    } catch (err) {
      onNotice(`删除失败：${err.message}`);
    }
  }, [onNotice]);

  useEffect(() => { loadSessions(); loadDocs(); }, [loadSessions, loadDocs]);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, profileReady]);

  function submitProfile() {
    const topic = profileDraft.topic.trim();
    const learningGoal = profileDraft.learning_goal.trim();
    if (!topic || !learningGoal) {
      onNotice("请先填写学习主题和学习目标。");
      return;
    }
    const normalizedProfile = {
      ...profileDraft,
      topic,
      learning_goal: learningGoal,
      constraints: profileDraft.constraints.trim(),
    };
    setUserProfile(normalizedProfile);
    setProfileReady(true);
  }

  async function send() {
    const text = input.trim();
    if (!text || isSending || !profileReady) return;
    setInput("");
    setIsSending(true);

    setMessages((items) => [
      ...items,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);

    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId || null,
          user_profile: userProfile,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error("响应流不可用");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          let event;
          try {
            event = JSON.parse(line);
          } catch {
            continue;
          }
          if (event.event === "start" && event.data?.session_id) {
            setSessionId(event.data.session_id);
          }
          if (event.event === "delta") {
            setMessages((items) => {
              const copy = [...items];
              const last = copy[copy.length - 1] || { role: "assistant", content: "" };
              copy[copy.length - 1] = { ...last, content: last.content + event.data.text };
              return copy;
            });
          }
          if (event.event === "done") {
            loadSessions();
          }
          if (event.event === "error") {
            throw new Error(event.data?.message || "请求失败");
          }
        }
      }
    } catch (err) {
      onNotice(err.message);
      setMessages((items) => {
        const copy = [...items];
        copy[copy.length - 1] = { role: "assistant", content: `请求失败：${err.message}` };
        return copy;
      });
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className={`workspace chat-workspace ${hidden ? "view-hidden" : ""}`}>
      <div className="chat-toolbar">
        <button className="secondary" onClick={() => setShowSessionList(!showSessionList)}>
          <History size={16} />
          {sessionId ? sessionId.slice(-12) : "新会话"}
        </button>
        <button className="secondary" onClick={newSession}>
          <Plus size={16} /> 新建
        </button>
        <button className="secondary" onClick={loadSessions}>
          <RefreshCcw size={16} />
        </button>
        <button className="secondary" onClick={() => setShowUpload(!showUpload)}>
          <Plus size={16} /> 上传 PDF
        </button>
        {userProfile ? <span className="profile-chip">{userProfile.topic}</span> : null}
        {uploadedDocs.slice(0, 3).map((d) => (
          <DocChip key={d.document_id} doc={d} onRemove={handleRemoveDoc} />
        ))}
      </div>

      {showUpload && (
        <PdfUpload onUploaded={handleDocUploaded} />
      )}

      {showSessionList && (
        <div className="session-dropdown">
          {sessions.map((s) => (
            <button
              key={s.session_id}
              className={s.session_id === sessionId ? "active" : ""}
              onClick={() => switchSession(s.session_id)}
            >
              <span className="session-preview">{s.preview || s.profile?.topic || "空会话"}</span>
              <small>{s.message_count} 条 · {s.last_updated?.slice(0, 10)}</small>
            </button>
          ))}
          {!sessions.length && <span className="muted" style={{ padding: 12 }}>暂无历史会话</span>}
        </div>
      )}

      <div className="messages" ref={scrollRef}>
        {!profileReady ? (
          <ProfileSetup value={profileDraft} onChange={setProfileDraft} onSubmit={submitProfile} />
        ) : null}

        {profileReady && !messages.length ? (
          <div className="empty-state">
            <BookOpen size={42} />
            <h2>开始对话</h2>
            <p>画像已建立。输入第一个问题，AI 会按你的学习目标和偏好来回答。</p>
          </div>
        ) : null}

        {messages.map((msg, i) => (
          <article key={i} className={`message ${msg.role}`}>
            <div className="message-role">{msg.role === "user" ? "你" : "AI"}</div>
            <div className="message-body">
              <Markdown>{msg.content}</Markdown>
            </div>
          </article>
        ))}
      </div>

      {profileReady ? (
        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="输入你的问题..."
          />
          <button onClick={send} disabled={isSending || !input.trim()}>
            {isSending ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
            发送
          </button>
        </div>
      ) : null}
    </section>
  );
}
