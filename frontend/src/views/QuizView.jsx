import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  History,
  Loader2,
  Pencil,
  RefreshCcw,
  Save,
  Send,
  Trash2,
  XCircle,
} from "lucide-react";

import { api } from "../api.js";

const QUESTION_TYPES = [
  { id: "single_choice", label: "单选题" },
  { id: "multiple_choice", label: "多选题" },
  { id: "true_false", label: "判断题" },
  { id: "fill_blank", label: "填空题" },
];

export function QuizView({ onNotice }) {
  const [topic, setTopic] = useState("");
  const [questionCount, setQuestionCount] = useState(5);
  const [selectedTypes, setSelectedTypes] = useState(["single_choice", "true_false"]);
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [userAnswers, setUserAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [evaluation, setEvaluation] = useState(null);
  const [expanded, setExpanded] = useState(new Set());

  // Session history state
  const [sessions, setSessions] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load session list on mount
  const loadSessions = useCallback(async () => {
    try {
      const data = await api("/api/v1/quiz/sessions");
      setSessions(data.sessions || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  // ── Generate ──

  async function generate() {
    if (!topic.trim()) {
      onNotice("请输入学习主题");
      return;
    }
    setLoading(true);
    setQuestions([]);
    setUserAnswers({});
    setSubmitted(false);
    setEvaluation(null);
    setExpanded(new Set());

    try {
      const data = await api("/api/v1/quiz/generate", {
        method: "POST",
        body: JSON.stringify({
          topic: topic.trim(),
          question_count: questionCount,
          question_types: selectedTypes.map(t => ({single_choice:"选择题",multiple_choice:"多选题",true_false:"判断题",fill_blank:"填空题"})[t] || t).join("、"),
          difficulty: "中等",
        }),
      });
      setQuestions(data.questions || []);
      setSessionId(data.session_id || "");
      setShowHistory(false);
      loadSessions();
      if (!data.questions?.length) {
        onNotice("未能生成题目，请重试");
      }
    } catch (err) {
      onNotice(`生成失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  // ── Save in-progress ──

  async function saveProgress() {
    if (!sessionId || !questions.length) return;
    setSaving(true);
    try {
      await api(`/api/v1/quiz/sessions/${encodeURIComponent(sessionId)}/save`, {
        method: "POST",
        body: JSON.stringify({
          topic,
          questions,
          user_answers: userAnswers,
        }),
      });
      onNotice("进度已保存");
      loadSessions();
    } catch (err) {
      onNotice(`保存失败: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  // ── Load a past session ──

  async function loadSession(sid) {
    try {
      const data = await api(`/api/v1/quiz/sessions/${encodeURIComponent(sid)}`);
      setQuestions(data.questions || []);
      setUserAnswers(data.user_answers || {});
      setSessionId(data.session_id || sid);
      setTopic(data.topic || "");
      setSubmitted(data.status === "completed");
      setEvaluation(data.evaluation || null);
      setExpanded(new Set());
      setShowHistory(false);
    } catch (err) {
      onNotice(`加载失败: ${err.message}`);
    }
  }

  // ── Delete a session ──

  async function deleteSession(sid) {
    try {
      await api(`/api/v1/quiz/sessions/${encodeURIComponent(sid)}`, { method: "DELETE" });
      setSessions((items) => items.filter((s) => s.session_id !== sid));
      if (sessionId === sid) reset();
    } catch (err) {
      onNotice(`删除失败: ${err.message}`);
    }
  }

  // ── Answer ──

  function setAnswer(qId, value) {
    setUserAnswers((prev) => ({ ...prev, [qId]: value }));
  }

  // ── Submit / Evaluate ──

  async function submitAnswers() {
    if (Object.keys(userAnswers).length < questions.length) {
      onNotice("请先回答所有题目");
      return;
    }
    try {
      const data = await api("/api/v1/quiz/evaluate", {
        method: "POST",
        body: JSON.stringify({
          questions,
          user_answers: userAnswers,
          session_id: sessionId,
        }),
      });
      setEvaluation(data);
      setSubmitted(true);
      loadSessions();
    } catch (err) {
      onNotice(`批改失败: ${err.message}`);
    }
  }

  // ── Reset ──

  function reset() {
    setQuestions([]);
    setUserAnswers({});
    setSubmitted(false);
    setEvaluation(null);
    setExpanded(new Set());
    setSessionId("");
    setTopic("");
  }

  function toggleExpand(qId) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(qId)) next.delete(qId);
      else next.add(qId);
      return next;
    });
  }

  // ── Render option ──

  function renderOption(q, opt) {
    const qId = q.id;
    const selected = userAnswers[qId] === opt.id;
    let className = "quiz-option";
    if (selected) className += " selected";

    if (submitted) {
      const isCorrect = opt.id === q.answer;
      const userWrong = selected && !isCorrect;
      if (isCorrect) className += " correct";
      if (userWrong) className += " wrong";
    }

    const handleClick = () => {
      if (submitted) return;
      if (q.type === "true_false" || q.type === "single_choice") {
        setAnswer(qId, opt.id);
      } else if (q.type === "multiple_choice") {
        const current = (userAnswers[qId] || "").split(",").filter(Boolean);
        const idx = current.indexOf(opt.id);
        if (idx >= 0) current.splice(idx, 1);
        else current.push(opt.id);
        setAnswer(qId, current.sort().join(","));
      }
    };

    return (
      <button key={opt.id} className={className} onClick={handleClick}>
        <span className="quiz-opt-id">{opt.id}</span>
        <span>{opt.text}</span>
        {submitted && opt.id === q.answer && (
          <CheckCircle2 size={16} className="quiz-opt-icon" />
        )}
        {submitted && selected && opt.id !== q.answer && (
          <XCircle size={16} className="quiz-opt-icon" />
        )}
      </button>
    );
  }

  // ── Render ──

  return (
    <section className="workspace quiz-workspace">
      {/* ── History bar (visible when have sessions) ── */}
      {sessions.length > 0 && !questions.length && (
        <div className="quiz-history-bar">
          <button className="secondary" onClick={() => setShowHistory(!showHistory)}>
            <History size={16} />
            {showHistory ? "收起历史" : `历史记录 (${sessions.length})`}
          </button>
        </div>
      )}

      {/* ── Session history dropdown ── */}
      {showHistory && (
        <div className="quiz-session-list">
          {sessions.map((s) => (
            <div key={s.session_id} className="quiz-session-item">
              <div className="quiz-session-info" onClick={() => loadSession(s.session_id)}>
                <span className="quiz-session-topic">{s.topic || s.preview || "未命名"}</span>
                <span className="quiz-session-meta">
                  <span className={`quiz-session-status ${s.status}`}>
                    {s.status === "completed" ? "已完成" : "进行中"}
                  </span>
                  {s.score != null && (
                    <span className={`quiz-session-score ${s.score >= 60 ? "pass" : "fail"}`}>
                      {s.score} 分
                    </span>
                  )}
                  <span>{s.question_count} 题</span>
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

      {/* ── Input ── */}
      {!questions.length && !loading && (
        <div className="quiz-input-card">
          <div className="quiz-input-header">
            <Pencil size={24} />
            <div>
              <h2>智能题目生成</h2>
              <p>输入学习主题，AI 根据知识库自动生成练习题。</p>
            </div>
          </div>
          <div className="quiz-input-fields">
            <label className="quiz-field quiz-field-wide">
              <span>学习主题</span>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="例如：机器学习基础、线性代数"
              />
            </label>
            <label className="quiz-field">
              <span>题目数量</span>
              <input
                type="number"
                min={1}
                max={20}
                value={questionCount}
                onChange={(e) => setQuestionCount(parseInt(e.target.value) || 5)}
              />
            </label>
          </div>
          {/* ── Question type selector ── */}
          <div className="quiz-type-selector">
            <span className="quiz-type-label">题目类型：</span>
            <div className="quiz-type-options">
              {QUESTION_TYPES.map((qt) => (
                <button
                  key={qt.id}
                  className={`quiz-type-chip ${selectedTypes.includes(qt.id) ? "active" : ""}`}
                  onClick={() => {
                    setSelectedTypes((prev) =>
                      prev.includes(qt.id)
                        ? prev.filter((t) => t !== qt.id)
                        : [...prev, qt.id]
                    );
                  }}
                >
                  {qt.label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <button onClick={generate} disabled={!selectedTypes.length}>
              <Send size={16} /> 生成题目
            </button>
          </div>
        </div>
      )}

      {/* ── In-progress save bar ── */}
      {questions.length > 0 && !submitted && (
        <div className="quiz-save-bar">
          <Clock size={14} />
          <span>答题进行中</span>
          <button className="secondary" onClick={saveProgress} disabled={saving}>
            <Save size={14} /> {saving ? "保存中..." : "保存进度"}
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="quiz-loading">
          <Loader2 size={24} className="spin" />
          <span>AI 正在生成题目...</span>
        </div>
      )}

      {/* ── Questions ── */}
      {questions.length > 0 && (
        <div className="quiz-questions">
          <div className="quiz-header-bar">
            <Pencil size={18} />
            <strong>{topic}</strong>
            <span className="quiz-header-sep">|</span>
            <span>{questions.length} 道题</span>
            {evaluation && (
              <>
                <span className="quiz-header-sep">|</span>
                <span className={evaluation.score >= 60 ? "quiz-score-pass" : "quiz-score-fail"}>
                  得分: {evaluation.score} 分
                </span>
                <span className="quiz-header-sep">|</span>
                <span className="quiz-weak">
                  薄弱点: {evaluation.weak_points?.join(", ") || "无"}
                </span>
              </>
            )}
            <button className="secondary" onClick={reset} style={{ marginLeft: "auto" }}>
              <RefreshCcw size={14} /> 重新生成题目
            </button>
          </div>

          <div className="quiz-list">
            {questions.map((q, i) => (
              <div key={q.id} className="quiz-card">
                <div className="quiz-card-header" onClick={() => toggleExpand(q.id)}>
                  <span className="quiz-q-number">{i + 1}</span>
                  <div className="quiz-q-meta">
                    <span className="quiz-q-type">{q.type === "single_choice" ? "单选" : q.type === "true_false" ? "判断" : q.type === "multiple_choice" ? "多选" : q.type}</span>
                    <span className="quiz-q-diff">{"★".repeat(q.difficulty || 1)}</span>
                  </div>
                  <span className="quiz-q-stem">{q.stem}</span>
                  {submitted && (
                    <span className={`quiz-q-result ${userAnswers[q.id] === q.answer ? "pass" : "fail"}`}>
                      {userAnswers[q.id] === q.answer ? "✓" : "✗"}
                    </span>
                  )}
                  {expanded.has(q.id) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </div>

                {expanded.has(q.id) && (
                  <div className="quiz-card-body">
                    {q.options && (
                      <div className="quiz-options">
                        {q.options.map((opt) => renderOption(q, opt))}
                      </div>
                    )}
                    {!q.options && (
                      <input
                        className="quiz-fill-input"
                        placeholder="输入你的答案"
                        value={userAnswers[q.id] || ""}
                        onChange={(e) => setAnswer(q.id, e.target.value)}
                        disabled={submitted}
                      />
                    )}
                    {submitted && (
                      <div className="quiz-explanation">
                        <strong>答案：</strong>{q.answer}
                        <br />
                        <strong>解析：</strong>{q.explanation}
                        {q.knowledge_point && (
                          <><br /><strong>知识点：</strong>{q.knowledge_point}</>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {!submitted && (
            <button className="quiz-submit-btn" onClick={submitAnswers}>
              <CheckCircle2 size={18} /> 提交答案
            </button>
          )}

          {evaluation && (
            <div className="quiz-eval-card">
              <div className="quiz-eval-header">
                <span className="quiz-eval-score">{evaluation.score} 分</span>
                <span>正确 {evaluation.correct_count}/{evaluation.total_count}</span>
              </div>
              {evaluation.weak_points?.length > 0 && (
                <div className="quiz-eval-weak">
                  <strong>薄弱知识点：</strong>
                  {evaluation.weak_points.join("、")}
                </div>
              )}
              <div className="quiz-eval-suggestions">
                <strong>复习建议：</strong>
                <ul>
                  {evaluation.suggestions?.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Empty ── */}
      {!questions.length && !loading && !showHistory && (
        <div className="quiz-empty">
          <Pencil size={48} />
          <h3>还没有生成题目</h3>
          <p>输入学习主题开始生成题目，或点击上方查看历史记录。</p>
        </div>
      )}
    </section>
  );
}
