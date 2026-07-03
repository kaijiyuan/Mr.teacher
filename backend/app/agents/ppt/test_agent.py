"""本地验证 PPTAgent 的脚本。

用法：
  cd backend
  python -m app.agents.ppt.test_agent

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
    """模拟 LLM 服务：返回预设的 PPT 大纲 JSON。"""

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
        prompt_text = str(prompt)

        # 判断是摘要 prompt 还是大纲 prompt
        if "摘要" in prompt_text or "summary" in prompt_text.lower():
            return self.FakeResponse(
                "本复习 PPT 围绕机器学习基础的核心概念展开，涵盖监督学习、"
                "决策树和激活函数等关键知识点，帮助学习者系统巩固理论基础。"
            )

        # 默认返回大纲
        mock_slides = [
            {
                "title": "机器学习概述",
                "bullets": [
                    "机器学习是人工智能的核心分支",
                    "主要分为监督学习、无监督学习和强化学习",
                    "监督学习使用标注数据进行训练",
                ],
                "speaker_notes": "先介绍基本概念，让学习者对机器学习有整体认识。",
                "source_chunks": ["chunk_001"],
            },
            {
                "title": "监督学习",
                "bullets": [
                    "定义：使用带有标签的训练数据学习输入到输出的映射",
                    "常见算法：线性回归、决策树、SVM、神经网络",
                    "评估指标：准确率、精确率、召回率、F1 分数",
                ],
                "speaker_notes": "重点讲解监督学习的核心思想，结合实际案例帮助理解。",
                "source_chunks": ["chunk_001"],
            },
            {
                "title": "决策树算法",
                "bullets": [
                    "决策树是一种监督学习算法",
                    "通过树形结构进行决策",
                    "优点：可解释性强，不需要特征缩放",
                ],
                "speaker_notes": "这是薄弱知识点，需要重点复习。强调决策树是监督学习而非无监督学习。",
                "source_chunks": ["chunk_001"],
            },
            {
                "title": "激活函数",
                "bullets": [
                    "Sigmoid：输出范围 (0,1)，用于二分类",
                    "ReLU：正区间线性，缓解梯度消失",
                    "Tanh：输出范围 (-1,1)，零中心化",
                ],
                "speaker_notes": "讲解激活函数的作用和各自特点，可以配合图示说明。",
                "source_chunks": ["chunk_002"],
            },
        ]
        return self.FakeResponse(json.dumps(mock_slides, ensure_ascii=False))

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
            {
                "chunk_id": "chunk_003",
                "text": "决策树通过树形结构进行决策，每个内部节点表示一个特征测试，叶节点表示类别。优点是可解释性强，不需要特征缩放。",
                "score": 0.78,
                "page": 5,
            },
        ]

    async def get_document(self, document_id: str) -> dict | None:
        return None

    def list_documents(self) -> list[dict]:
        return []


async def main():
    print("=" * 60)
    print("PPTAgent 本地验证")
    print("=" * 60)

    # 1. 注册 fake 服务
    from app.core.runtime import ServiceRegistry, AgentRuntime

    registry = ServiceRegistry()
    registry.register("llm", FakeLLMService())
    registry.register("knowledge", FakeKnowledgeService())
    runtime = AgentRuntime(services=registry)

    # 2. 创建 PPTAgent
    from app.agents.ppt.agent import PPTAgent

    agent = PPTAgent()

    # 3. 构造输入（含 quiz_evaluation 模拟答题评估结果）
    inputs = {
        "knowledge_base_id": "kb_test_001",
        "topic": "机器学习基础",
        "slide_count": 4,
        "user_profile": {"topic": "机器学习", "knowledge_level": "学过但不熟"},
        "key_points": [
            {"title": "监督学习", "summary": "使用标签数据训练"},
            {"title": "决策树", "summary": "基于规则的分类方法"},
            {"title": "激活函数", "summary": "Sigmoid、ReLU 等"},
        ],
        "quiz_evaluation": {
            "score": 60.0,
            "correct_count": 3,
            "total_count": 5,
            "weak_points": ["决策树"],
            "suggestions": ["建议重点复习决策树"],
        },
    }

    print(f"\n[输入]: {json.dumps(inputs, ensure_ascii=False, indent=2)}")

    # 4. 执行 Agent
    print("\n[生成中] 正在生成 PPT 大纲...")
    result = await agent.process(inputs, runtime)

    # 5. 检查结果
    print(f"\n[输出]:")
    print(f"   error: {result.error}")

    if result.error:
        print(f"[失败] Agent 运行失败: {result.error.message}")
        return

    state = result.state_update
    outline = state.get("ppt_outline", {})
    artifact_id = state.get("ppt_artifact_id", "")

    print(f"   ppt_artifact_id: {artifact_id}")
    print(f"   ppt_file_path: {state.get('ppt_file_path', '')}")
    print(f"   标题: {outline.get('title', '')}")
    print(f"   幻灯片数: {outline.get('slide_count', 0)}")
    print(f"   摘要: {outline.get('summary', '')}")
    print(f"   是否有 Artifact: {len(result.artifacts) > 0}")

    # 验证 .pptx 文件是否已生成
    ppt_path = state.get("ppt_file_path", "")
    if ppt_path:
        from pathlib import Path as _Path
        if _Path(ppt_path).exists():
            file_size = _Path(ppt_path).stat().st_size
            print(f"   PPTX 文件已生成: {ppt_path} ({file_size} 字节)")
        else:
            print(f"   [警告] PPTX 文件路径存在但文件未找到: {ppt_path}")

    for i, slide in enumerate(outline.get("slides", []), 1):
        print(f"\n  -- 第 {i} 页: {slide.get('title', '')} --")
        for bullet in slide.get("bullets", []):
            print(f"     - {bullet}")
        notes = slide.get("speaker_notes", "")
        if notes:
            print(f"     [讲稿] {notes[:60]}{'...' if len(notes) > 60 else ''}")

    print("\n[完成] 验证通过!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
