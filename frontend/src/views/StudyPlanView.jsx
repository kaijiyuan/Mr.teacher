import { useEffect, useState } from "react";
import {
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  GraduationCap,
  Loader2,
  RefreshCcw,
  Send,
  Target,
  TrendingUp,
} from "lucide-react";

import { api } from "../api.js";

const TYPE_COLORS = {
  "学习": "#156f5b",
  "练习": "#f0a030",
  "复习": "#4a90d9",
  "综合": "#8e44ad",
};

const TYPE_ICONS = {
  "学习": GraduationCap,
  "练习": TrendingUp,
  "复习": FileText,
  "综合": CheckCircle2,
};

export function StudyPlanView({ onNotice }) {
  const [topic, setTopic] = useState("");
  const [goal, setGoal] = useState("系统学习并掌握核心知识");
  const [level, setLevel] = useState("初学者");
  const [dailyTime, setDailyTime] = useState(2);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [expandedDays, setExpandedDays] = useState(new Set());
  const [profileLoaded, setProfileLoaded] = useState(false);

  // Auto-load profile from chat on mount
  useEffect(() => {
    api("/api/v1/profile")
      .then((data) => {
        const p = data.profile;
        if (p && p.topic) {
          setTopic(p.topic || "");
          setLevel(p.knowledge_level || "初学者");
          setGoal(p.learning_goal || "系统学习并掌握核心知识");
          // Parse time_available like "每天 30 分钟" -> 0.5
          if (p.time_available) {
            const m = p.time_available.match(/\d+/);
            const mins = m ? parseInt(m[0]) : 0;
            if (p.time_available.includes("分钟") && mins > 0) {
              setDailyTime(mins / 60);
            } else if (p.time_available.includes("小时") && mins > 0) {
              setDailyTime(mins);
            }
          }
          if (!profileLoaded) setProfileLoaded(true);
        }
      })
      .catch(() => {});
  }, []);

  async function generate() {
    if (!topic.trim()) {
      onNotice("请输入学习主题");
      return;
    }
    setLoading(true);
    setResult(null);

    try {
      const data = await api("/api/v1/plan/generate", {
        method: "POST",
        body: JSON.stringify({
          topic: topic.trim(),
          goal,
          level,
          daily_time: dailyTime,
        }),
      });
      setResult(data);
    } catch (err) {
      onNotice(`生成失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function toggleDay(day) {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
      return next;
    });
  }

  const plan = result?.plan || [];
  const summary = result?.summary;

  return (
    <section className="workspace plan-workspace">
      {/* ── Input section ── */}
      {!result && !loading && (
        <div className="plan-input-card">
          <div className="plan-input-header">
            <Calendar size={24} />
            <div>
              <h2>学习计划</h2>
              <p>输入学习主题和画像，AI 自动生成个性化学习时间计划表。</p>
            </div>
          </div>

          <div className="plan-profile-fields">
            {profileLoaded && (
              <div className="plan-profile-badge">
                <RefreshCcw size={12} />
                已自动加载对话页面学习画像
              </div>
            )}
            <label className="plan-profile-field plan-field-wide">
              <span>学习主题</span>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="例如：机器学习基础、线性代数"
              />
            </label>
            <label className="plan-profile-field">
              <span>当前水平</span>
              <select
                value={level}
                onChange={(e) => setLevel(e.target.value)}
                className="plan-select"
              >
                <option value="初学者">初学者</option>
                <option value="了解基础">了解基础</option>
                <option value="中等水平">中等水平</option>
                <option value="进阶">进阶</option>
              </select>
            </label>
            <label className="plan-profile-field">
              <span>每天可用时间（小时）</span>
              <input
                type="number"
                min={0.5}
                max={8}
                step={0.5}
                value={dailyTime}
                onChange={(e) => setDailyTime(parseFloat(e.target.value) || 2)}
              />
            </label>
            <label className="plan-profile-field plan-field-wide">
              <span>学习目标</span>
              <input
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="系统学习并掌握核心知识"
              />
            </label>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <button onClick={generate} disabled={!topic.trim()}>
              <Send size={16} /> 生成计划
            </button>
          </div>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="plan-loading">
          <Loader2 size={24} className="spin" />
          <span>AI 正在生成学习计划...</span>
        </div>
      )}

      {/* ── Result ── */}
      {result && !loading && (
        <div className="plan-result">
          {/* Summary bar */}
          <div className="plan-summary-card">
            <div className="plan-summary-row">
              <Target size={20} />
              <div>
                <strong>{summary?.topic}</strong>
                <p>{summary?.goal}</p>
              </div>
            </div>
            <div className="plan-summary-stats">
              <div className="plan-summary-stat">
                <span className="plan-stat-value">{summary?.total_days || 0} 天</span>
                <span className="plan-stat-label">学习周期</span>
              </div>
              <div className="plan-summary-stat">
                <span className="plan-stat-value">{summary?.level}</span>
                <span className="plan-stat-label">当前水平</span>
              </div>
              <div className="plan-summary-stat">
                <span className="plan-stat-value">~{summary?.daily_time}h/天</span>
                <span className="plan-stat-label">每日投入</span>
              </div>
            </div>
            {summary?.weak_points?.length > 0 && (
              <div className="plan-weak-summary">
                <strong>薄弱知识点：</strong> {summary.weak_points.join("、")}
              </div>
            )}
          </div>

          {/* Timeline */}
          <div className="plan-timeline">
            {plan.map((day) => {
              const isExpanded = expandedDays.has(day.day);
              const TypeIcon = TYPE_ICONS[day.type] || GraduationCap;
              const color = TYPE_COLORS[day.type] || "#156f5b";

              return (
                <div key={day.day} className="plan-day-card">
                  <div className="plan-day-header" onClick={() => toggleDay(day.day)}>
                    <div className="plan-day-dot" style={{ background: color }}>
                      <TypeIcon size={14} color="#fff" />
                    </div>
                    <div className="plan-day-info">
                      <span className="plan-day-label">{day.date_label || `第${day.day}天`}</span>
                      <span className="plan-day-topic">{day.topic}</span>
                    </div>
                    <span className="plan-day-type" style={{ color }}>
                      {day.type}
                    </span>
                    <span className="plan-day-duration">
                      <Clock size={12} /> {day.duration}
                    </span>
                    {expandedDays.has(day.day) ? (
                      <ChevronUp size={16} />
                    ) : (
                      <ChevronDown size={16} />
                    )}
                  </div>

                  {isExpanded && (
                    <div className="plan-day-body">
                      <div className="plan-day-goal">
                        <Target size={14} />
                        <span>{day.goal}</span>
                      </div>
                      {day.content?.length > 0 && (
                        <ul className="plan-day-content">
                          {day.content.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Empty ── */}
      {!result && !loading && (
        <div className="plan-empty">
          <Calendar size={48} />
          <h3>还没有学习计划</h3>
          <p>填写学习画像，点击"生成计划"开始。</p>
        </div>
      )}
    </section>
  );
}
