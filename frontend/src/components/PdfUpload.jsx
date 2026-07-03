import { useEffect, useRef, useState } from "react";
import { FileUp, Loader2, CheckCircle, XCircle, FileText } from "lucide-react";

import { API_BASE, api } from "../api.js";

export function PdfUpload({ onUploaded }) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null); // { ok, message, doc }
  const [dragOver, setDragOver] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // tick elapsed timer while uploading
  useEffect(() => {
    if (!uploading) { setElapsed(0); return; }
    const id = setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [uploading]);

  async function doUpload(file) {
    if (!file) return;
    setUploading(true);
    setResult(null);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 900_000); // 15 min timeout
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/v1/knowledge/upload`, {
        method: "POST",
        body: form,
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "上传失败");
      setResult({
        ok: true,
        message: `「${file.name}」解析完成`,
        doc: data,
      });
      if (onUploaded) onUploaded(data);
    } catch (err) {
      clearTimeout(timeout);
      if (err.name === "AbortError") {
        setResult({ ok: false, message: "解析超时（超过 15 分钟）。请检查 MinerU API Key 是否正确配置，或 PDF 是否过大。" });
      } else {
        setResult({ ok: false, message: err.message });
      }
    } finally {
      setUploading(false);
    }
  }

  function onFileChange(e) {
    const f = e.target.files?.[0];
    if (f) doUpload(f);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) doUpload(f);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept=".pdf"
        style={{ display: "none" }}
        onChange={onFileChange}
      />

      {/* upload area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? "#156f5b" : "#dde3e5"}`,
          borderRadius: 12,
          padding: "18px 16px",
          textAlign: "center",
          cursor: "pointer",
          background: dragOver ? "#e5f3ef" : "#fafbfc",
          transition: "border-color 0.2s, background 0.2s",
        }}
      >
        {uploading ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "#156f5b" }}>
            <Loader2 size={18} className="spin" />
            正在解析 PDF…（已等待 {elapsed} 秒，最长 15 分钟）
          </span>
        ) : (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "#68737a" }}>
            <FileUp size={18} />
            点击或拖拽上传 PDF
          </span>
        )}
      </div>

      {/* result toast */}
      {result && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 10,
            borderRadius: 10,
            padding: "10px 14px",
            background: result.ok ? "#e5f3ef" : "#fef0f0",
            border: `1px solid ${result.ok ? "#a3d9c8" : "#f5c6c6"}`,
            fontSize: 13,
          }}
        >
          {result.ok ? <CheckCircle size={16} color="#0f604f" /> : <XCircle size={16} color="#c0392b" />}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, color: result.ok ? "#0f604f" : "#a33" }}>
              {result.message}
            </div>
            {result.doc && (
              <div style={{ marginTop: 4, color: "#4a555c", lineHeight: 1.5 }}>
                {result.doc.document_metadata && (
                  <>
                    页数：{result.doc.document_metadata.page_count}
                    {" · "}内容块：{result.doc.document_metadata.chunk_count}
                  </>
                )}
                {result.doc.document_summary && (
                  <div style={{ marginTop: 4, fontStyle: "italic" }}>
                    {result.doc.document_summary.slice(0, 120)}
                    {result.doc.document_summary.length > 120 ? "…" : ""}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* quick doc list (loaded externally) */}
    </div>
  );
}

/** Small chip showing info for an already-uploaded document. */
export function DocChip({ doc, onRemove }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 999,
        background: "#e5f3ef",
        color: "#0f604f",
        padding: "2px 10px 2px 6px",
        fontSize: 12,
        fontWeight: 600,
        maxWidth: 220,
      }}
    >
      <FileText size={14} />
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {doc.file_name || doc.document_id?.slice(-8)}
      </span>
      {onRemove && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(doc.document_id); }}
          style={{
            background: "transparent",
            border: 0,
            cursor: "pointer",
            color: "#0f604f",
            padding: 0,
            lineHeight: 1,
            fontSize: 14,
            minHeight: 0,
          }}
          title="移除"
        >
          ×
        </button>
      )}
    </span>
  );
}
