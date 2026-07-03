import { BookOpen, Check } from "lucide-react";

import { CustomSelect } from "./CustomSelect.jsx";

export const PROFILE_DEFAULTS = {
  topic: "",
  knowledge_level: "了解一点",
  learning_goal: "",
  time_available: "每天 30 分钟",
  learning_style: "循序渐进，多举例",
  scenario: "课程学习",
  constraints: "",
  source_scope: "当前对话",
};

export function ProfileSetup({ value, onChange, onSubmit }) {
  const setField = (key, nextValue) => onChange({ ...value, [key]: nextValue });

  const levelOptions = ["完全不了解", "了解一点", "学过但不熟", "比较熟悉"];
  const styleOptions = ["循序渐进，多举例", "先讲概念，再练习", "多提问引导", "直接给结论"];
  const scenarioOptions = ["课程学习", "考试复习", "项目实践", "工作应用", "兴趣了解"];

  return (
    <div className="profile-setup">
      <div className="profile-heading">
        <BookOpen size={34} />
        <div>
          <h2>你想学点什么？</h2>
          <p>先建立一个学习画像，后续答疑会按你的基础、目标和偏好来讲。</p>
        </div>
      </div>

      <div className="profile-grid">
        <label className="profile-field profile-field-wide">
          <span>学习主题</span>
          <input
            value={value.topic}
            onChange={(e) => setField("topic", e.target.value)}
            placeholder="例如：机器学习、线性代数、React、产品设计"
          />
        </label>

        <label className="profile-field">
          <span>当前基础</span>
          <CustomSelect
            value={value.knowledge_level}
            options={levelOptions}
            onChange={(nextValue) => setField("knowledge_level", nextValue)}
          />
        </label>

        <label className="profile-field">
          <span>学习场景</span>
          <CustomSelect
            value={value.scenario}
            options={scenarioOptions}
            onChange={(nextValue) => setField("scenario", nextValue)}
          />
        </label>

        <label className="profile-field profile-field-wide">
          <span>学习目标</span>
          <textarea
            value={value.learning_goal}
            onChange={(e) => setField("learning_goal", e.target.value)}
            placeholder="例如：两周内能理解核心概念，并完成一个小项目"
          />
        </label>

        <label className="profile-field">
          <span>可投入时间</span>
          <input
            value={value.time_available}
            onChange={(e) => setField("time_available", e.target.value)}
            placeholder="例如：每天 30 分钟"
          />
        </label>

        <label className="profile-field">
          <span>资料范围</span>
          <CustomSelect
            value={value.source_scope}
            options={["当前对话", "上传资料优先", "知识库和联网搜索"]}
            onChange={(nextValue) => setField("source_scope", nextValue)}
          />
        </label>

        <label className="profile-field profile-field-wide">
          <span>讲解偏好</span>
          <div className="segmented-options">
            {styleOptions.map((item) => (
              <button
                key={item}
                type="button"
                className={value.learning_style === item ? "active" : ""}
                onClick={() => setField("learning_style", item)}
              >
                {item}
              </button>
            ))}
          </div>
        </label>

        <label className="profile-field profile-field-wide">
          <span>补充约束</span>
          <textarea
            value={value.constraints}
            onChange={(e) => setField("constraints", e.target.value)}
            placeholder="例如：希望少用公式、需要中文解释、要结合考试题型"
          />
        </label>
      </div>

      <div className="profile-actions">
        <button onClick={onSubmit}>
          <Check size={18} />
          开始学习
        </button>
      </div>
    </div>
  );
}
