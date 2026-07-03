import { useEffect, useState } from "react";
import { RefreshCcw, Trash2 } from "lucide-react";

import { api } from "../api.js";
import { Markdown } from "../components/Markdown.jsx";

export function HistoryView({ onNotice }) {
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState("");
  const [messages, setMessages] = useState([]);

  async function loadSessions() {
    try {
      const data = await api("/api/v1/sessions");
      setSessions(data.sessions || []);
    } catch (err) {
      onNotice(err.message);
    }
  }

  async function loadMessages(sid) {
    setSelected(sid);
    try {
      const data = await api(`/api/v1/sessions/${encodeURIComponent(sid)}/messages`);
      setMessages(data.messages || []);
    } catch (err) {
      onNotice(err.message);
    }
  }

  async function deleteSession(sid) {
    if (!window.confirm(`删除会话 ${sid.slice(-12)}？`)) return;
    try {
      await api(`/api/v1/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" });
      setSessions((items) => items.filter((s) => s.session_id !== sid));
      if (selected === sid) {
        setSelected("");
        setMessages([]);
      }
    } catch (err) {
      onNotice(err.message);
    }
  }

  useEffect(() => { loadSessions(); }, []);

  return (
    <section className="workspace history-layout">
      <div className="panel session-list">
        <div className="panel-header">
          <h2>历史会话</h2>
          <button className="secondary" onClick={loadSessions}><RefreshCcw size={16} />刷新</button>
        </div>
        {sessions.map((s) => (
          <button
            key={s.session_id}
            className={selected === s.session_id ? "active" : ""}
            onClick={() => loadMessages(s.session_id)}
          >
            <strong>{s.preview || s.profile?.topic || "空会话"}</strong>
            <span>{s.last_updated}</span>
            <small>{s.message_count} 条消息</small>
            <Trash2
              size={14}
              style={{ marginLeft: "auto" }}
              onClick={(e) => { e.stopPropagation(); deleteSession(s.session_id); }}
            />
          </button>
        ))}
        {!sessions.length ? <p className="muted">暂无历史会话。</p> : null}
      </div>
      <div className="panel history-messages">
        {messages.map((msg, i) => (
          <article key={i} className={`message ${msg.role}`}>
            <div className="message-role">{msg.role}</div>
            <div className="message-body"><Markdown>{msg.content}</Markdown></div>
          </article>
        ))}
        {!messages.length ? <p className="muted">选择一个会话查看内容。</p> : null}
      </div>
    </section>
  );
}
