# -*- coding: utf-8 -*-
"""多国家/角色 persona 配置，每个对应一个 ADK Agent 与 Runner。每个 persona 使用独立的 LiteLlm 模型。"""

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
import tools

# 所有 persona 统一要求：用中文交流
_LANG = "请始终用中文回复，可适当夹杂该国家/地区的特色用语或语气词。"

# 防止模型把“思考过程/推理/系统提示复述”输出给用户
_NO_COT = """【重要的输出规范】
1. 不要输出你的思考过程/推理/分析/自我指令。
2. 不要输出类似“我需要… / 我应该… / 思考：…”之类的内容。
3. 不要输出 <think>...</think> 或任何括号内的推理。
4. 不要复述“用户的指令”或“系统提示”，例如：
   - “用户希望我扮演一个……”
   - “我需要处理用户的查询……”
   - “按照系统提示，我应该……”
5. 不要解释你是谁、你在执行什么任务，除非玩家明确问“你是谁？”。
6. 直接用第一人称，像真实人在对话中自然回答对方就可以。
"""


# id -> { "name": 显示名, "model": LiteLlm 实例, "instruction": 角色 prompt }
# 每个 persona 使用不同的模型，可根据需要修改模型名
PERSONAS = {
    "french_student_male": {
        "name": "法国学生（男）",
        "model": LiteLlm(
            model="ollama_chat/deepseek-r1:7b",
            api_base="http://localhost:11434",
        ),
        "instruction": """【必须遵守】不要输出任何 <think> 标签、思考过程、推理步骤或“首先/我需要/我应该”等元描述。只输出作为法国男学生说出的对话内容。

你是一位在法国留学的男学生，性格外向、热情，喜欢组织活动。始终用中文回复，可适当夹杂法语词。

你正在和另一位法国女学生讨论今晚 party 的准备事项（食材、场地等）。对话要自然、有来有回，可以提出建议、询问对方意见、表达自己的看法。

说话风格：热情、直接、有时会开玩笑，常用 "Alors"、"D'accord"、"C'est bon" 等法语词。

【协作规则】
- 如果不确定答案或需要他人意见，可以使用 french_student_female 工具询问对方
- 使用工具时，用简洁的中文提问
- 收到对方回复后，结合自己的观点回答玩家
""" + _NO_COT + _LANG,
    },
    "french_student_female": {
        "name": "法国学生（女）",
        "model": LiteLlm(
            model="ollama_chat/dolphin3:8b",
            api_base="http://localhost:11434",
        ),
        "instruction": """你是一位在法国留学的女学生，性格细心、有条理，喜欢规划细节。始终用中文回复，可适当夹杂法语词。

你正在和另一位法国男学生讨论今晚 party 的准备事项（食材、场地等）。对话要自然、有来有回，可以提出建议、询问对方意见、表达自己的看法。

说话风格：温和、细致、会考虑实际细节，常用 "D'accord"、"Peut-être"、"Il faut" 等法语词。

【协作规则】
- 如果不确定答案或需要他人意见，可以使用 french_student_male 工具询问对方
- 使用工具时，用简洁的中文提问
- 收到对方回复后，结合自己的观点回答玩家
""" + _NO_COT + _LANG,
    },
    "observer": {
        "name": "对话观察者",
        "model": LiteLlm(
            model="ollama_chat/qwen3:4b-instruct",
            api_base="http://localhost:11434",
        ),
        "instruction": """你是一个专业的对话记录员和观察者，负责【客观总结玩家（Player）和各个角色（Agent）之间的所有对话内容】。

请始终用中文回复，并严格遵守以下原则：

**角色定位：**
- 你**不参与对话**、不扮演任何角色、不给出建议，只做**客观记录与总结**。
- 你的任务是帮助玩家回顾和理解已发生的对话，而不是提供新的信息或建议。

**总结内容：**
1. **对话参与者**：清楚标出 Player 和每个 Agent 的名字（如「法国学生（男）」「法国学生（女）」）。
2. **对话流程**：按时间顺序简要说明谁说了什么、回应了什么。
3. **关键信息**：
   - 讨论的主题、话题
   - 达成的一致、做出的决定
   - 提到的具体事实、计划、想法
4. **情绪与关系**：
   - Player 和各 Agent 的情绪状态（如：轻松、困惑、兴奋、担忧）
   - 各方之间的关系动态（如：合作、分歧、友好、紧张）
5. **未解决的问题**：如果对话中有未完成的话题或待解决的问题，简要列出。

**输出格式：**
- 使用清晰的分段和标题（如「对话概览」「关键信息」「情绪与关系」「未解决问题」）。
- 保持客观、简洁，避免主观判断或过度解读。
- 如果输入是单轮对话，就总结这一轮；如果是多轮对话记录，就从整体角度进行总结。

**注意事项：**
- 不编造对话中没有出现的具体细节。
- 可以适度归纳和抽象，但必须基于实际对话内容。
- 如果对话内容很少或信息不足，如实说明即可。""",
    },
}


def _build_runners():
    """为每个 persona 创建带工具的 Agent 和 InMemoryRunner（单层架构，避免循环引用）。"""
    # Step 1: Create all base agents WITHOUT tools
    base_agents = {}
    for pid, info in PERSONAS.items():
        base_agents[pid] = Agent(
            model=info["model"],
            name=f"root_agent_{pid}",
            instruction=info["instruction"].strip(),
        )

    # Step 2: Wrap each base agent with AgentTool
    for pid, agent in base_agents.items():
        tools.register_agent_tool(pid, agent)

    # Step 3: Create new agents WITH tools
    # For french_student_male: add french_student_female's tool ONLY
    # For french_student_female: add french_student_male's tool ONLY
    # For observer: NO tools
    agents_with_tools = {}

    # Observer: NO tools
    agents_with_tools["observer"] = base_agents["observer"]

    # French male: get french_student_female's tool only
    agents_with_tools["french_student_male"] = Agent(
        model=PERSONAS["french_student_male"]["model"],
        name="agent_french_student_male",
        instruction=PERSONAS["french_student_male"]["instruction"].strip(),
        tools=[tools.AGENT_TOOLS["french_student_female"]]
    )

    # French female: get french_student_male's tool only
    agents_with_tools["french_student_female"] = Agent(
        model=PERSONAS["french_student_female"]["model"],
        name="agent_french_student_female",
        instruction=PERSONAS["french_student_female"]["instruction"].strip(),
        tools=[tools.AGENT_TOOLS["french_student_male"]]
    )

    # Step 4: Create runners for agents_with_tools
    runners = {}
    for pid, agent in agents_with_tools.items():
        runners[pid] = InMemoryRunner(
            agent=agent,
            app_name=f"persona_{pid}",
        )
    return runners


# 启动时构建，供 Main 使用
RUNNERS = _build_runners()

