"""本地验证 QuizAgent 的脚本。

用法：
  cd backend
  python -m app.agents.quiz.test_agent

原理：
  - 用 FakeLLMService（返回模拟 JSON）代替真实 LLM
  - 用 FakeKnowledgeService（返回模拟搜索结果）代替真实知识库
  - 不依赖任何外部 API，可以离线运行
"""

from __future__ import annotations

import json
import sys
from typing import Any
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class FakeLLMService:
    """模拟 LLM 服务：返回预设的题目 JSON。"""

    model_name = "fake-model"

    class FakeChoice:
        class FakeMessage:
            def __init__(self, content: str):
                self.content = content

        def __init__(self, content: str):
            self.message = self.FakeMessage(content)

    class FakeResponse:
        def __init__(self, content: str):
            self.choices = [FakeLLMService.FakeChoice(content)]

    async def ainvoke(
        self,
        prompt: Any,
        *,
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> FakeResponse:
        mock_questions = [
            {
                "id": "q_1",
                "type": "single_choice",
                "stem": "机器学习中，监督学习需要以下哪项？",
                "options": [
                    {"id": "A", "text": "标注好的训练数据"},
                    {"id": "B", "text": "无标签的数据"},
                    {"id": "C", "text": "强化信号"},
                    {"id": "D", "text": "生成式模型"},
                ],
                "answer": "A",
                "explanation": "监督学习依赖有标签的样本进行训练。",
                "knowledge_point": "监督学习",
                "difficulty": 2,
            },
            {
                "id": "q_2",
                "type": "true_false",
                "stem": "决策树是一种无监督学习算法。",
                "options": [
                    {"id": "A", "text": "正确"},
                    {"id": "B", "text": "错误"},
                ],
                "answer": "B",
                "explanation": "决策树是监督学习算法，需要标签来划分节点。",
                "knowledge_point": "决策树",
                "difficulty": 1,
            },
            {
                "id": "q_3",
                "type": "fill_blank",
                "stem": "在神经网络中，_____函数将输入映射到 0 到 1 之间。",
                "options": None,
                "answer": "Sigmoid",
                "explanation": "Sigmoid 函数的输出范围是 (0, 1)。",
                "knowledge_point": "激活函数",
                "difficulty": 2,
            },
        ]
        return self.FakeResponse(json.dumps(mock_questions, ensure_ascii=False))

    async def astream(self, prompt, *, model, temperature, max_tokens):
        yield await self.ainvoke(prompt, model=model, temperature=temperature, max_tokens=max_tokens)


class FakeKnowledgeService:
    """模拟知识库服务：返回固定搜索结果。"""

    async def search(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
    ) -> list[dict]:
        return [
            {
                "chunk_id": "chunk_001",
                "text": "监督学习（Supervised Learning）使用带有标签的训练数据来学习输入到输出的映射。常见算法包括线性回归、决策树、SVM 和神经网络。",
                "score": 0.92,
                "page": 1,
            },
            {
                "chunk_id": "chunk_002",
                "text": "激活函数是神经网络中的重要组成部分。Sigmoid 函数输出范围为 (0,1)，常用于二分类输出层。ReLU 函数在正区间保持线性，有效缓解梯度消失。",
                "score": 0.85,
                "page": 3,
            },
        ]

    async def get_document(self, document_id: str) -> dict | None:
        return None

    def list_documents(self) -> list[dict]:
        return []


async def main():
    print("=" * 60)
    print("QuizAgent 本地验证")
    print("=" * 60)

    # 1. 注册 fake 服务
    from app.core.runtime import ServiceRegistry, AgentRuntime

    registry = ServiceRegistry()
    registry.register("llm", FakeLLMService())
    registry.register("knowledge", FakeKnowledgeService())
    runtime = AgentRuntime(services=registry)

    # 2. 创建 QuizAgent
    from app.agents.quiz.agent import QuizAgent

    agent = QuizAgent()

    # 3. 构造输入
    inputs = {
        "knowledge_base_id": "kb_test_001",
        "topic": "机器学习基础",
        "question_count": 3,
        "question_types": "选择题、判断题、填空题",
        "difficulty": "简单到中等",
        "user_profile": {"topic": "机器学习", "knowledge_level": "了解一点"},
        "key_points": [
            {"title": "监督学习", "summary": "使用标签数据训练"},
            {"title": "激活函数", "summary": "Sigmoid、ReLU 等"},
            {"title": "决策树", "summary": "基于规则的分类方法"},
        ],
    }

    print(f"\n[输入]: {json.dumps(inputs, ensure_ascii=False, indent=2)}")

    # 4. 执行 Agent
    print("\n[生成中] 正在生成题目...")
    result = await agent.process(inputs, runtime)

    # 5. 检查结果
    print(f"\n[输出]:")
    print(f"   error: {result.error}")

    if result.error:
        print(f"[失败] Agent 运行失败: {result.error.message}")
        return

    state = result.state_update
    questions = state.get("questions", [])
    quiz_session_id = state.get("quiz_session_id", "")
    metadata = state.get("quiz_metadata", {})

    print(f"   quiz_session_id: {quiz_session_id}")
    print(f"   metadata: {json.dumps(metadata, ensure_ascii=False, indent=2)}")
    print(f"   题目数量: {len(questions)}")
    print(f"   是否有 Artifact: {len(result.artifacts) > 0}")

    for q in questions:
        print(f"\n  -- {q['id']} ({q['type']}) --")
        print(f"     题干: {q['stem']}")
        if q.get("options"):
            for opt in q["options"]:
                print(f"     {opt['id']}. {opt['text']}")
        print(f"     答案: {q['answer']}")
        print(f"     解析: {q['explanation']}")
        print(f"     知识点: {q.get('knowledge_point', '')}")

    # 6. 测试 evaluator
    print("\n" + "=" * 60)
    print("测试 evaluate_simple 批改")
    print("=" * 60)

    from app.agents.quiz.evaluator import evaluate_simple

    # 模拟用户答题
    user_answers = {
        "q_1": "A",  # 正确
        "q_2": "A",  # 错误（正确答案是 B）
        "q_3": "Sigmoid",  # 正确
    }

    evaluation = evaluate_simple(questions, user_answers)
    print(f"\n   得分: {evaluation.score} 分")
    print(f"   正确: {evaluation.correct_count}/{evaluation.total_count}")
    print(f"   薄弱点: {evaluation.weak_points}")
    print(f"   建议: {evaluation.suggestions}")

    print(f"\n   逐题明细:")
    for d in evaluation.details:
        status = "PASS" if d["correct"] else "FAIL"
        print(f"     {status} {d['question_id']}: user={d['user_answer']}, correct={d['correct_answer']}")

    print("\n[完成] 验证通过!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
