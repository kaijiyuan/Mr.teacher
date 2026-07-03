import { useCallback, useEffect, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  History,
  Layers,
  Loader2,
  Presentation,
  Sliders,
  Trash2,
} from "lucide-react";

import { API_BASE, api } from "../api.js";

export function PlanView({ onNotice }) {
  const [topic, setTopic] = useState("");
  const [slideCount, setSlideCount] = useState(10);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [expandedSlides, setExpandedSlides] = useState(new Set());

  // Document / mindmap state
  const [docs, setDocs] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [mindmap, setMindmap] = useState(null);
  const [loadingMindmap, setLoadingMindmap] = useState(false);
  const [useMindmap, setUseMindmap] = useState(false);

  // Session history state
  const [sessions, setSessions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load sessions + docs on mount
  const loadSessions = useCallback(async () => {
    try {
      const data = await api("/api/v1/ppt/sessions");
      setSessions(data.sessions || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadSessions(); api("/api/v1/knowledge/documents").then((d) => setDocs(d.documents || [])).catch(() => {}); }, [loadSessions]);

  // Load mindmap when a document is selected
  useEffect(() => {
    if (!selectedDoc) { setMindmap(null); return; }
    setLoadingMindmap(true);
    setMindmap(null);
    const controller = new AbortController();
    fetch(`${API_BASE}/api/v1/knowledge/documents/${encodeURIComponent(selectedDoc.document_id)}/mindmap`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data) => { setMindmap(data.mindmap || null); setLoadingMindmap(false); setTopic(selectedDoc.file_name?.replace(/\.pdf$/i, "") || ""); })
      .catch((err) => { if (err.name !== "AbortError") setLoadingMindmap(false); });
    return () => controller.abort();
  }, [selectedDoc]);

  async function generate() {
    if (!topic.trim()) { onNotice("请输入学习主题"); return; }
    setLoading(true);
    setResult(null);

    let keyPoints = [];
    if (useMindmap && mindmap?.key_points) {
      keyPoints = mindmap.key_points.map((kp) => ({ title: kp.title || "", summary: kp.description || "" }));
    }
    if (useMindmap && mindmap?.nodes && keyPoints.length === 0) {
      keyPoints = mindmap.nodes.map((n) => ({ title: n.title || "", summary: n.summary || "" }));
    }

    try {
      const data = await api("/api/v1/ppt/generate", {
        method: "POST",
        body: JSON.stringify({
          topic: topic.trim(),
          slide_count: slideCount,
          knowledge_base_id: selectedDoc?.knowledge_base_id || "",
          key_points: keyPoints,
        }),
      });
      setResult(data);
      loadSessions();
    } catch (err) {
      onNotice(`生成失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  // ── Load a past session ──

  async function loadSession(sid) {
    try {
      const data = await api(`/api/v1/ppt/sessions/${encodeURIComponent(sid)}`);
      setResult({
        ppt_artifact_id: data.ppt_artifact_id || "",
        ppt_outline: data.ppt_outline || {},
        ppt_file_path: data.ppt_file_path || "",
      });
      setTopic(data.topic || "");
      setSlideCount(data.slide_count || 10);
      setExpandedSlides(new Set());
      setShowHistory(false);
    } catch (err) {
      onNotice(`加载失败: ${err.message}`);
    }
  }

  // ── Delete a session ──

  async function deleteSession(sid) {
    try {
      await api(`/api/v1/ppt/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" });
      setSessions((items) => items.filter((s) => s.session_id !== sid));
    } catch (err) {
      onNotice(`删除失败: ${err.message}`);
    }
  }

  function toggleSlide(index) {
    setExpandedSlides((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index); else next.add(index);
      return next;
    });
  }

  function getDownloadUrl() {
    // Prefer exact filename for download (avoids old file caching issues)
    if (result?.ppt_file_name) {
      return `${API_BASE}/api/v1/ppt/file/${encodeURIComponent(result.ppt_file_name)}/download`;
    }
    if (!result?.ppt_artifact_id) return "";
    return `${API_BASE}/api/v1/ppt/${encodeURIComponent(result.ppt_artifact_id)}/download`;
  }

  function handleDocSelect(doc) {
    if (selectedDoc?.document_id === doc.document_id) { setSelectedDoc(null); setUseMindmap(false); }
    else { setSelectedDoc(doc); setUseMindmap(true); }
  }

  function resetView() {
    setResult(null);
    setTopic("");
    setSlideCount(10);
    setExpandedSlides(new Set());
  }

  const outline = result?.ppt_outline;
  const slides = outline?.slides || [];

  return (
    <section className="workspace plan-workspace">
      {/* ── History bar ── */}
      {sessions.length > 0 && (
        <div className="plan-history-bar">
          <button className="secondary" onClick={() => setShowHistory(!showHistory)}>
            <History size={16} />
            {showHistory ? "收起历史" : `历史记录 (${sessions.length})`}
          </button>
        </div>
      )}

      {/* ── Session history dropdown ── */}
      {showHistory && (
        <div className="plan-session-list">
          {sessions.map((s) => (
            <div key={s.session_id} className="plan-session-item">
              <div className="plan-session-info" onClick={() => loadSession(s.session_id)}>
                <span className="plan-session-topic">{s.topic || s.preview || "未命名"}</span>
                <span className="plan-session-meta">
                  <span>{s.slide_count} 页</span>
                  <span>{s.last_updated?.slice(0, 16).replace("T", " ")}</span>
                </span>
              </div>
              <button className="secondary icon-button" onClick={() => deleteSession(s.session_id)} title="删除">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          {!sessions.length && <p className="muted" style={{ padding: 12 }}>暂无记录</p>}
        </div>
      )}

      {/* ── Input section ── */}
      {!result && !loading && (
        <div className="plan-input-card">
          <div className="plan-input-header">
            <Presentation size={24} />
            <div>
              <h2>生成复习 PPT</h2>
              <p>可选择已有文档的思维导图辅助生成，或直接输入主题。</p>
            </div>
          </div>

          {docs.length > 0 && (
            <div className="plan-doc-selector">
              <span className="plan-doc-label"><Layers size={14} />基于文档（思维导图）：</span>
              <div className="plan-doc-chips">
                <button className={`plan-doc-chip ${!selectedDoc ? "active" : ""}`} onClick={() => { setSelectedDoc(null); setUseMindmap(false); }}>不使用文档</button>
                {docs.map((d) => (
                  <button key={d.document_id} className={`plan-doc-chip ${selectedDoc?.document_id === d.document_id ? "active" : ""}`} onClick={() => handleDocSelect(d)}>
                    <FileText size={13} />{d.file_name || d.document_id.slice(-8)}
                  </button>
                ))}
              </div>
              {loadingMindmap && <span className="plan-mindmap-loading"><Loader2 size={12} className="spin" /> 加载思维导图...</span>}
              {useMindmap && mindmap && <span className="plan-mindmap-info"><Layers size={12} />{mindmap.nodes?.length || 0} 个知识点{mindmap.key_points?.length > 0 && ` · ${mindmap.key_points.length} 个核心知识点`}</span>}
            </div>
          )}

          <div className="plan-input-fields">
            <label className="plan-field plan-field-wide">
              <span>学习主题</span>
              <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="例如：机器学习基础、线性代数" disabled={loading} />
            </label>
            <label className="plan-field">
              <span><Sliders size={14} />最多页数</span>
              <input type="number" min={3} max={30} value={slideCount} onChange={(e) => setSlideCount(parseInt(e.target.value) || 10)} disabled={loading} />
            </label>
            <div className="plan-field" style={{ justifyContent: "flex-end" }}>
              <button onClick={generate} disabled={loading || !topic.trim()}>
                {loading ? <><Loader2 size={18} className="spin" /> 生成中...</> : <><Check size={18} /> 生成 PPT</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && <div className="plan-loading"><Loader2 size={24} className="spin" /><span>AI 正在生成 PPT 大纲...</span></div>}

      {/* ── Result section ── */}
      {result && !loading && (
        <div className="plan-result">
          <div className="plan-summary-bar">
            <FileText size={18} />
            <strong>{outline?.title || topic}</strong>
            <span className="plan-summary-sep">|</span>
            <span>{slides.length} 页幻灯片</span>
            {useMindmap && selectedDoc && <><span className="plan-summary-sep">|</span><span className="plan-summary-text">基于文档: {selectedDoc.file_name}</span></>}
            {outline?.summary && <><span className="plan-summary-sep">|</span><span className="plan-summary-text">{outline.summary}</span></>}
            {result.ppt_file_path && <a href={getDownloadUrl()} className="plan-download-btn" download><Download size={16} />下载 .pptx</a>}
            <button className="secondary" onClick={resetView} style={{ marginLeft: 8 }}><Trash2 size={14} /> 清除</button>
          </div>

          <div className="plan-slide-list">
            {slides.map((slide, i) => (
              <div key={i} className="plan-slide-card">
                <div className="plan-slide-header" onClick={() => toggleSlide(i)}>
                  <div className="plan-slide-number">{i + 1}</div>
                  <span className="plan-slide-title">{slide.title}</span>
                  <span className="plan-slide-bullet-count">{slide.bullets?.length || 0} 要点</span>
                  {expandedSlides.has(i) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </div>
                {expandedSlides.has(i) && (
                  <div className="plan-slide-body">
                    {slide.bullets?.length > 0 && <ul className="plan-bullet-list">{slide.bullets.map((b, j) => <li key={j}>{b}</li>)}</ul>}
                    {slide.speaker_notes && <div className="plan-speaker-notes"><strong>讲稿提示：</strong>{slide.speaker_notes}</div>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Empty state ── */}
      {!result && !loading && !showHistory && (
        <div className="plan-empty">
          <Presentation size={48} />
          <h3>还没有生成过 PPT</h3>
          <p>选择文档或输入主题，点击"生成 PPT"开始，或查看历史记录。</p>
        </div>
      )}
    </section>
  );
}
