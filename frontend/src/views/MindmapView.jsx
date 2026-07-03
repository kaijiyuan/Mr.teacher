import { useEffect, useState } from "react";
import {
  BrainCircuit, ChevronDown, ChevronRight, Layers, Loader2, RefreshCw, Star,
  Clock, FileText,
} from "lucide-react";

import { API_BASE, api } from "../api.js";

/** Fetch mindmap from backend. Pass force=true to bypass cache. */
async function fetchMindmap(documentId, signal, force = false) {
  const res = await fetch(
    `${API_BASE}/api/v1/knowledge/documents/${encodeURIComponent(documentId)}/mindmap`,
    { signal, method: force ? "POST" : "GET" }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** Recursive tree node component. */
function TreeNode({ node, depth = 0 }) {
  const [open, setOpen] = useState(depth < 2);

  const colors = ["#0f604f", "#156f5b", "#1a7f69", "#208f77", "#269f85"];
  const barColor = colors[Math.min(depth, colors.length - 1)];

  return (
    <div style={{ marginLeft: depth === 0 ? 0 : 16, marginBottom: 4 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          cursor: "pointer",
          padding: "8px 12px",
          borderRadius: 10,
          borderLeft: `4px solid ${barColor}`,
          background: depth === 0 ? "#e5f3ef" : depth === 1 ? "#f8fbfa" : "#fff",
          transition: "background 0.15s",
        }}
      >
        {node.children?.length > 0 ? (
          open ? <ChevronDown size={16} color={barColor} /> : <ChevronRight size={16} color={barColor} />
        ) : (
          <span style={{ width: 16 }} />
        )}
        <span style={{ fontWeight: 600, fontSize: 14, color: "#1e2329" }}>
          {node.title}
        </span>
        {node.importance >= 4 && <Star size={14} color="#f0a030" fill="#f0a030" />}
        {node.importance && (
          <span style={{ fontSize: 11, color: "#68737a", marginLeft: "auto" }}>
            {"★".repeat(node.importance)}
          </span>
        )}
      </div>

      {open && node.summary && (
        <div style={{ marginLeft: 40, padding: "4px 0 8px", fontSize: 13, color: "#4a555c" }}>
          {node.summary}
        </div>
      )}

      {open && node.children?.map((child) => (
        <TreeNode key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

/** Main mindmap view. */
export function MindmapView({ hidden }) {
  const [docs, setDocs] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [mindmap, setMindmap] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fromCache, setFromCache] = useState(false);

  function loadMindmap(force) {
    if (!selectedDoc) return;
    setLoading(true);
    setError("");
    setMindmap(null);
    const controller = new AbortController();
    fetchMindmap(selectedDoc.document_id, controller.signal, force)
      .then((data) => {
        setMindmap(data.mindmap);
        setFromCache(!!data.cached);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== "AbortError") { setError(err.message); setLoading(false); }
      });
    return () => controller.abort();
  }

  // Load documents list
  useEffect(() => {
    api("/api/v1/knowledge/documents")
      .then((data) => setDocs(data.documents || []))
      .catch(() => {});
  }, []);

  // Load mindmap (cached) when a document is selected
  useEffect(() => {
    if (!selectedDoc) return;
    const cleanup = loadMindmap(false);
    return cleanup;
  }, [selectedDoc]);

  // If no docs, show upload prompt
  if (!docs.length) {
    return (
      <section className={hidden ? "view-hidden" : "placeholder-section"}>
        <div className="empty-state">
          <BrainCircuit size={42} />
          <h2>知识图谱</h2>
          <p>先上传 PDF 文档，再点击生成思维导图。</p>
        </div>
      </section>
    );
  }

  return (
    <section className={`workspace ${hidden ? "view-hidden" : ""}`} style={{ display: "flex", flexDirection: "column", gap: 16, padding: "18px 24px" }}>
      {/* Document selector */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600, color: "#1e2329", fontSize: 14 }}>选择文档：</span>
        {docs.map((d) => (
          <button
            key={d.document_id}
            className={`secondary ${selectedDoc?.document_id === d.document_id ? "active" : ""}`}
            onClick={() => setSelectedDoc(d)}
            style={{
              background: selectedDoc?.document_id === d.document_id ? "#e5f3ef" : undefined,
              color: selectedDoc?.document_id === d.document_id ? "#0f604f" : undefined,
            }}
          >
            <FileText size={14} />
            {d.file_name || d.document_id.slice(-8)}
          </button>
        ))}
        {selectedDoc && (
          <button className="secondary" onClick={() => loadMindmap(true)} disabled={loading}
                  title="强制重新生成">
            <RefreshCw size={14} className={loading ? "spin" : ""} />
            重新生成
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 40, gap: 10, color: "#156f5b" }}>
          <Loader2 size={20} className="spin" />
          <span>正在生成思维导图…</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ padding: "12px 16px", borderRadius: 10, background: "#fef0f0", border: "1px solid #f5c6c6", color: "#a33", fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Mindmap tree + key points side by side */}
      {mindmap && !loading && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20, flex: 1, minHeight: 0, overflow: "auto" }}>
          {/* Tree */}
          <div style={{ overflow: "auto", paddingRight: 16 }}>
            <h3 style={{ margin: "0 0 12px", color: "#1e2329", fontSize: 18 }}>
              <Layers size={18} style={{ verticalAlign: -3, marginRight: 6 }} />
              {mindmap.title || "思维导图"}
              {fromCache && (
                <span style={{ fontSize: 11, color: "#68737a", fontWeight: 400, marginLeft: 8 }}>
                  (来自缓存)
                </span>
              )}
            </h3>
            {mindmap.nodes?.map((node, i) => (
              <TreeNode key={node.id || i} node={node} depth={0} />
            ))}
          </div>

          {/* Key points sidebar */}
          <div style={{ overflow: "auto", borderLeft: "1px solid #e8ecef", paddingLeft: 20 }}>
            <h3 style={{ margin: "0 0 12px", color: "#1e2329", fontSize: 16 }}>
              <Star size={16} style={{ verticalAlign: -3, marginRight: 6 }} />
              核心知识点
            </h3>
            {mindmap.key_points?.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {mindmap.key_points.map((kp, i) => (
                  <div
                    key={i}
                    style={{
                      borderRadius: 10,
                      border: "1px solid #dde3e5",
                      padding: "10px 14px",
                      background: "#fafbfc",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, fontSize: 14, color: "#1e2329" }}>
                        {kp.title}
                      </span>
                      <span style={{ fontSize: 11, color: "#68737a", marginLeft: "auto" }}>
                        难度 {"★".repeat(kp.difficulty || 1)}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: "#4a555c", lineHeight: 1.5 }}>
                      {kp.description}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "#68737a", fontSize: 13 }}>暂无知识点。</div>
            )}

            {mindmap.nodes?.[0]?.source_chunks?.length > 0 && (
              <div style={{ marginTop: 16, fontSize: 11, color: "#68737a" }}>
                <Clock size={12} style={{ verticalAlign: -2, marginRight: 4 }} />
                基于 {mindmap.nodes[0].source_chunks.length} 个内容块生成
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
