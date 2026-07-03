import { useState } from "react";
import {
  BrainCircuit,
  Check,
  HelpCircle,
  History,
  MessageSquareText,
  Network,
  Presentation,
  Settings,
} from "lucide-react";

import { Placeholder } from "./components/Placeholder.jsx";
import { ChatView } from "./views/ChatView.jsx";
import { HistoryView } from "./views/HistoryView.jsx";
import { MindmapView } from "./views/MindmapView.jsx";
import { PlanView } from "./views/PlanView.jsx";
import { QuizView } from "./views/QuizView.jsx";
import { StudyPlanView } from "./views/StudyPlanView.jsx";

export function App() {
  const [activeView, setActiveView] = useState("chat");
  const [notice, setNotice] = useState("");

  const views = [
    ["chat", MessageSquareText, "对话"],
    ["history", History, "历史"],
    ["plan", Check, "计划"],
    ["quiz", HelpCircle, "题目生成"],
    ["ppt", Presentation, "PPT"],
    ["kg", Network, "图谱"],
    ["settings", Settings, "设置"],
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <BrainCircuit size={24} />
          <div>
            <strong>AI Chat</strong>
            <span>智能学习助手</span>
          </div>
        </div>

        <nav className="nav">
          {views.map(([key, Icon, label]) => (
            <button
              key={key}
              className={activeView === key ? "active" : ""}
              onClick={() => setActiveView(key)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>AI Chat</h1>
            <p>带学习画像和记忆能力的答疑助手</p>
          </div>
        </header>

        {notice ? (
          <div className="notice">
            <span>{notice}</span>
            <button onClick={() => setNotice("")}>关闭</button>
          </div>
        ) : null}

        <ChatView hidden={activeView !== "chat"} onNotice={setNotice} />
        {activeView === "history" && <HistoryView onNotice={setNotice} />}
        {activeView === "plan" && <StudyPlanView onNotice={setNotice} />}
        {activeView === "quiz" && <QuizView onNotice={setNotice} />}
        {activeView === "ppt" && <PlanView onNotice={setNotice} />}
        {activeView === "kg" && <MindmapView hidden={false} />}
        {activeView === "settings" && <Placeholder title="设置" icon={Settings} />}
      </main>
    </div>
  );
}
