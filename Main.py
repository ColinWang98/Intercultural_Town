import re
import uuid
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.genai import types

# 加载环境变量（必须在 import personas 之前）
from dotenv import load_dotenv
load_dotenv()  # 从 .env 文件加载环境变量

import personas  # 在加载环境变量后导入

# 多 persona：每个角色独立 session，切换即切换聊天对象
USER_ID = "godot"
DEFAULT_PERSONAS = ["mikko", "aino"]  # 默认使用芬兰学生双人组合

app = FastAPI()


@app.get("/")
def root():
    """根路径，避免浏览器/客户端访问时 404。"""
    return {
        "message": "ADK Chat API",
        "endpoints": [
            "GET /personas",
            "GET /conversations",
            "POST /conversations",
            "GET /conversations/{id}",
            "GET /conversations/{id}/messages",
            "POST /conversations/{id}/messages",
        ],
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """避免浏览器请求 favicon 时 404。"""
    from fastapi.responses import Response
    return Response(status_code=204)


class PersonaItem(BaseModel):
    id: str
    name: str


# ---------- RESTful: 会话与消息 ----------

class DynamicPersona(BaseModel):
    """动态 Persona 配置，允许在 Godot 中定义角色信息而无需修改后端代码"""
    id: str
    name: str
    gender: str = "Male"  # 性别：Male, Female, Non-binary, Other
    personality: str = ""  # 性格描述
    personality_type: str = "Extrovert"  # Extrovert, Introvert, Ambivert
    interests: str = ""  # 兴趣爱好
    speaking_style: str = ""  # 说话风格
    likes: list[str] = []  # 喜好列表
    dislikes: list[str] = []  # 不喜欢列表
    current_state: str = ""  # 当前状态
    location_hint: str = ""  # 地点提示


class CreateConversationReq(BaseModel):
    persona_ids: list[str]
    dynamic_personas: list[DynamicPersona] = []  # 动态 persona 配置（可选）


class PostMessageReq(BaseModel):
    content: str


# 单条消息：role=user 时 name 可为空；role=model 时为角色显示名
class MessageItem(BaseModel):
    role: str  # "user" | "model"
    name: str | None = None
    content: str


class ConversationItem(BaseModel):
    id: str
    persona_ids: list[str]
    messages: list[MessageItem]
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    persona_ids: list[str]
    created_at: str
    message_count: int


# 会话存储：id -> { persona_ids, messages, created_at, dynamic_personas }
CONVERSATIONS: dict[str, dict] = {}

# 会话状态管理：id -> {
#     "phase": "small_talk" | "religion_deep" | "allergy_deep" | "wrap_up" | "finished",
#     "religion_discussed": bool,
#     "allergy_discussed": bool,
#     "sub_agent_turns": int,  # 子代理讨论轮数计数
# }
CONVERSATION_STATES: dict[str, dict] = {}

# 单次回复最大字符数，避免超长/重复导致 Godot 不显示或卡顿
MAX_REPLY_LENGTH = 2000


def _format_conversation_history(messages: list[dict]) -> str:
    """将会话消息列表格式化为传给模型的文本（玩家: / 角色: ）。"""
    lines: list[str] = []
    for m in messages:
        role, name, content = m.get("role"), m.get("name"), m.get("content", "")
        if role == "user":
            lines.append(f"玩家: {content}")
        elif role == "model" and name:
            lines.append(f"{name}: {content}")
        elif content:
            lines.append(content)
    return "\n".join(lines)


def _generate_dynamic_persona_instruction(dynamic_persona: DynamicPersona) -> str:
    """生成动态 persona 的 AI 指令"""
    # 性别映射
    gender_map = {
        "Male": "男性",
        "Female": "女性",
        "Non-binary": "非二元性别",
        "Other": "其他性别"
    }
    gender_text = gender_map.get(dynamic_persona.gender, dynamic_persona.gender)

    # 性格类型映射
    personality_type_map = {
        "Extrovert": "外向热情",
        "Introvert": "内向文静",
        "Ambivert": "中立平衡"
    }
    personality_type_text = personality_type_map.get(dynamic_persona.personality_type, dynamic_persona.personality_type)

    # 构建基础指令
    instruction = f"""你是 **{dynamic_persona.name}**，{gender_text}。

"""
    # 添加性别相关提示
    if dynamic_persona.gender == "Male":
        instruction += "你是男性角色，请用男性的口吻说话。\n"
    elif dynamic_persona.gender == "Female":
        instruction += "你是女性角色，请用女性的口吻说话。\n"

    # 添加性格描述
    if dynamic_persona.personality:
        instruction += f"\n**性格**：{dynamic_persona.personality}\n"
    else:
        instruction += f"\n**性格类型**：{personality_type_text}\n"

    # 添加兴趣
    if dynamic_persona.interests:
        instruction += f"**兴趣爱好**：{dynamic_persona.interests}\n"

    # 添加说话风格
    if dynamic_persona.speaking_style:
        instruction += f"**说话风格**：{dynamic_persona.speaking_style}\n"

    # 添加喜好
    if dynamic_persona.likes:
        instruction += f"**喜好**：{', '.join(dynamic_persona.likes)}\n"

    # 添加不喜欢
    if dynamic_persona.dislikes:
        instruction += f"**不喜欢**：{', '.join(dynamic_persona.dislikes)}\n"

    # 添加当前状态
    if dynamic_persona.current_state:
        instruction += f"\n**当前状态**：{dynamic_persona.current_state}\n"

    # 添加地点提示
    if dynamic_persona.location_hint:
        instruction += f"**当前位置**：{dynamic_persona.location_hint}\n"

    instruction += "\n请严格按照上述角色设定进行对话。"

    return instruction

def _strip_thinking(text: str) -> str:
    """尽量移除模型输出中的"思考过程"片段（如 <think>...</think>，含大小写变体）。"""
    if not text:
        return text
    # DeepSeek R1 等推理模型会用 <think>/</think> 包裹推理，可能带大小写变体
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # 未闭合的 <think>：截掉该标签及之后内容
    match = re.search(r"<think>", text, re.IGNORECASE)
    if match:
        text = text[: match.start()]
    
    # 策略：找到角色对话开始的位置（如 "Mikko:", "Aino:", 或其他常见角色标识）
    # 对话通常以 "角色名:" 或 "【角色名】" 开头
    dialogue_patterns = [
        r"^(Mikko|Aino|观察者|Observer)\s*[:：]",  # "Mikko:" "Aino:" 等
        r"^【(Mikko|Aino|观察者|Observer)】",       # 【Mikko】等
    ]
    
    lines = text.split("\n")
    dialogue_start_idx = None
    
    # 找到第一个对话行
    for i, line in enumerate(lines):
        s = line.strip()
        for pattern in dialogue_patterns:
            if re.match(pattern, s, re.IGNORECASE):
                dialogue_start_idx = i
                break
        if dialogue_start_idx is not None:
            break
    
    # 如果找到对话开始位置，只保留从该位置开始的内容
    if dialogue_start_idx is not None:
        lines = lines[dialogue_start_idx:]
        return "\n".join(lines).strip()
    
    # 如果没找到明确的对话标识，使用旧的前缀过滤逻辑
    # 去掉以思考前缀开头的整行
    thinking_prefixes = (
        "思考：", "（思考）", "推理：", "【思考】", "（推理）",
        "好的，", "好，", "嗯，", "OK，", "Ok，", "ok，",
        "首先，", "接下来，", "然后，", "现在，",
        "用户希望", "用户想要", "用户需要", "用户请求", "用户提供",
        "我需要", "我应该", "我要", "我会",
        "让我", "我来", "最后，", "同时，", "另外，",
    )
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            out.append(line)
            continue
        is_thinking = any(s.startswith(prefix) for prefix in thinking_prefixes)
        if is_thinking:
            continue
        out.append(line)
    text = "\n".join(out).strip()
    return text


def _get_reply_from_events(events):
    """从 ADK 产生的 events 中拼接出 model 的最终文本回复。
    跳过已出现过的相同文本块（避免模型重复导致超长），并限制总长度。
    """
    parts = []
    seen = set()
    for evt in events:
        content = getattr(evt, "content", None)
        if not content:
            continue
        role = getattr(content, "role", None)
        if role != "model":
            continue
        for p in getattr(content, "parts", []) or []:
            text = getattr(p, "text", None)
            if not text:
                continue
            # 完全相同的整块只保留一次（避免同一句重复几百次）
            if text in seen:
                continue
            seen.add(text)
            parts.append(text)
    reply = _strip_thinking("".join(parts).strip()) or None
    if reply and len(reply) > MAX_REPLY_LENGTH:
        reply = reply[:MAX_REPLY_LENGTH].rstrip() + "…"
    return reply


def _session_id(persona_id: str, conversation_id: str | None = None) -> str:
    """ADK 会话 id：有 conversation_id 时用会话 id，否则用 default_{persona_id}。"""
    if conversation_id:
        return conversation_id
    return f"default_{persona_id}"


def _detect_focus_flags(user_content: str) -> tuple[bool, bool]:
    """检测玩家当前消息是否主动提到宗教/过敏相关话题。

    只检测玩家主动提出的话题，不扫描历史消息。
    
    Returns:
        (has_religion_focus, has_allergy_focus)
    """
    religion_keywords = [
        "宗教", "清真", "穆斯林", "伊斯兰", "犹太", "洁食", 
        "halal", "kosher", "斋月", "素食", "纯素", "vegan",
        "信仰", "禁忌", "不吃猪", "不吃牛",
    ]
    allergy_keywords = [
        "过敏", "花生", "坚果", "海鲜", "虾", "蟹", "贝类",
        "乳糖", "牛奶", "奶制品", "麸质", "gluten", "小麦",
        "不耐受", "敏感",
    ]

    content = user_content.lower()
    has_religion_focus = any(kw in content for kw in religion_keywords)
    has_allergy_focus = any(kw in content for kw in allergy_keywords)

    return has_religion_focus, has_allergy_focus


async def _get_or_create_session(runner, app_name: str, session_id: str):
    """获取或创建指定 persona 的 session。"""
    session = await runner.session_service.get_session(
        app_name=app_name, user_id=USER_ID, session_id=session_id
    )
    if session is None:
        session = await runner.session_service.create_session(
            app_name=app_name, user_id=USER_ID, session_id=session_id
        )
    return session


async def _run_chat_round(conversation_id: str, persona_ids: list[str], user_content: str) -> str:
    """在指定会话中追加用户消息，调用 ADK 生成回复并追加到会话，返回合并后的回复文本。

    状态机架构：
    - small_talk: 闲聊阶段，检测关键词
    - religion_deep: 宗教专家子代理主导
    - allergy_deep: 过敏专家子代理主导
    - wrap_up: 收尾阶段
    - finished: 完成，调用 Observer

    支持动态 persona：从会话中获取 dynamic_personas 配置。
    """
    conv = CONVERSATIONS.get(conversation_id)
    if not conv:
        raise ValueError(f"conversation not found: {conversation_id}")

    # 初始化会话状态
    if conversation_id not in CONVERSATION_STATES:
        CONVERSATION_STATES[conversation_id] = {
            "phase": "small_talk",
            "religion_discussed": False,
            "allergy_discussed": False,
            "sub_agent_turns": 0,
        }

    state = CONVERSATION_STATES[conversation_id]
    messages = conv["messages"]
    messages.append({"role": "user", "name": None, "content": user_content})

    # 获取动态 persona 映射表
    dynamic_personas_list = conv.get("dynamic_personas", [])
    dynamic_personas_map: dict[str, DynamicPersona] = {
        dp.id: dp for dp in dynamic_personas_list
    }

    # 获取当前状态
    phase = state["phase"]

    # === 状态机逻辑 ===
    if phase == "small_talk":
        # 只检测玩家当前消息是否主动提到相关话题
        has_religion, has_allergy = _detect_focus_flags(user_content)

        if has_religion and not state["religion_discussed"]:
            state["phase"] = "religion_deep"
            state["sub_agent_turns"] = 0
            phase = "religion_deep"  # 立即更新当前 phase
            print(f"[STATE] {conversation_id}: small_talk -> religion_deep")
        elif has_allergy and not state["allergy_discussed"]:
            state["phase"] = "allergy_deep"
            state["sub_agent_turns"] = 0
            phase = "allergy_deep"  # 立即更新当前 phase
            print(f"[STATE] {conversation_id}: small_talk -> allergy_deep")
        elif state["religion_discussed"] and state["allergy_discussed"]:
            state["phase"] = "wrap_up"
            phase = "wrap_up"  # 立即更新当前 phase
            print(f"[STATE] {conversation_id}: small_talk -> wrap_up")
        else:
            # 继续闲聊
            pass

    elif phase == "religion_deep":
        state["sub_agent_turns"] += 1
        # 3-4轮后返回
        if state["sub_agent_turns"] >= 3:
            state["religion_discussed"] = True
            if state["allergy_discussed"]:
                state["phase"] = "wrap_up"
            else:
                state["phase"] = "small_talk"
            print(f"[STATE] {conversation_id}: religion_deep -> {state['phase']}")

    elif phase == "allergy_deep":
        state["sub_agent_turns"] += 1
        # 3-4轮后返回
        if state["sub_agent_turns"] >= 3:
            state["allergy_discussed"] = True
            if state["religion_discussed"]:
                state["phase"] = "wrap_up"
            else:
                state["phase"] = "small_talk"
            print(f"[STATE] {conversation_id}: allergy_deep -> {state['phase']}")

    elif phase == "wrap_up":
        # 检测玩家是否确认
        user_lower = user_content.lower()
        affirmative_words = ["是", "好了", "可以", "没问题", "考虑清楚了", "没了", "没有"]
        if any(word in user_lower for word in affirmative_words):
            state["phase"] = "finished"
            print(f"[STATE] {conversation_id}: wrap_up -> finished")

    # === 根据状态调用对应的 Agent ===
    if phase == "small_talk":
        # 芬兰学生闲聊
        return await _finnish_students_respond(conversation_id, user_content, messages, dynamic_personas_map)
    elif phase == "religion_deep":
        # 宗教专家附身 Mikko
        expert_reply = await _expert_respond(
            conversation_id, user_content, messages,
            expert_id="religion_expert",
            expert_display_name="Mikko",
            dynamic_personas_map=dynamic_personas_map,
        )
        # Aino 可以补充（可选）
        aino_dynamic = dynamic_personas_map.get("aino")
        aino_reply = await _call_agent(
            conversation_id, "aino",
            f"【对话记录】\n{_format_conversation_history(messages)}\n\nMikko 刚刚说了关于宗教饮食禁忌的内容：{expert_reply}\n\n玩家说：{user_content}\n\n请简短回应或补充，1句话即可。",
            messages,
            aino_dynamic,
        )
        if aino_reply:
            aino_name = dynamic_personas_map.get("aino", DynamicPersona(name="Aino")).name
            return f"{expert_reply}\n\n{aino_name}: {aino_reply}"
        return expert_reply
    elif phase == "allergy_deep":
        # 过敏专家附身 Aino
        expert_reply = await _expert_respond(
            conversation_id, user_content, messages,
            expert_id="allergy_expert",
            expert_display_name="Aino",
            dynamic_personas_map=dynamic_personas_map,
        )
        # Mikko 可以补充（可选）
        mikko_dynamic = dynamic_personas_map.get("mikko")
        mikko_reply = await _call_agent(
            conversation_id, "mikko",
            f"【对话记录】\n{_format_conversation_history(messages)}\n\nAino 刚刚说了关于食物过敏的内容：{expert_reply}\n\n玩家说：{user_content}\n\n请简短回应或补充，1句话即可。",
            messages,
            mikko_dynamic,
        )
        if mikko_reply:
            mikko_name = dynamic_personas_map.get("mikko", DynamicPersona(name="Mikko")).name
            return f"{expert_reply}\n\n{mikko_name}: {mikko_reply}"
        return expert_reply
    elif phase == "wrap_up":
        # 芬兰学生收尾
        reply = await _finnish_students_respond(conversation_id, user_content, messages, dynamic_personas_map)
        # 如果已进入 finished，调用 Observer
        if state["phase"] == "finished":
            observer_reply = await _call_observer(conversation_id, messages)
            return f"{reply}\n\n{observer_reply}"
        return reply
    elif phase == "finished":
        # 已完成，只返回 Observer 总结
        return await _call_observer(conversation_id, messages)

    return "（对话状态异常，请重启会话）"


async def _call_agent(
    conversation_id: str,
    persona_id: str,
    prompt: str,
    messages: list[dict],
    dynamic_persona: DynamicPersona | None = None
) -> str:
    """调用单个 Agent。

    Args:
        conversation_id: 会话 ID
        persona_id: 角色 ID
        prompt: 提示文本
        messages: 消息列表
        dynamic_persona: 可选的动态 persona 配置
    """
    runner = personas.RUNNERS[persona_id]
    app_name = f"persona_{persona_id}"
    session_id = _session_id(persona_id, conversation_id)

    # 如果有动态 persona，使用动态 persona 的名字；否则使用预定义名字
    if dynamic_persona:
        persona_name = dynamic_persona.name
    else:
        persona_name = personas.PERSONAS[persona_id]["name"]

    await _get_or_create_session(runner, app_name, session_id)

    # 如果有动态 persona，将动态 persona 指令添加到提示中
    if dynamic_persona:
        dynamic_instruction = _generate_dynamic_persona_instruction(dynamic_persona)
        prompt = f"{dynamic_instruction}\n\n{prompt}"

    new_message = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = []
    async for evt in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=new_message
    ):
        events.append(evt)

        # Log tool call events
        if hasattr(evt, 'content') and evt.content:
            if hasattr(evt.content, 'parts'):
                for part in evt.content.parts or []:
                    if hasattr(part, 'function_call') and part.function_call is not None and getattr(part.function_call, 'name', None) is not None:
                        print(f"[TOOL CALL] {persona_name} -> {part.function_call.name}({part.function_call.args})")
                    elif hasattr(part, 'function_response') and part.function_response is not None and getattr(part.function_response, 'response', None) is not None:
                        print(f"[TOOL RESULT] {persona_name} <- {part.function_response.response}")

    ai_reply = _get_reply_from_events(events)
    if ai_reply:
        messages.append({"role": "model", "name": persona_name, "content": ai_reply})
        return ai_reply

    return ""


def _decide_speaker_order(messages: list[dict], user_content: str) -> list[str]:
    """动态决定发言顺序。
    
    规则：
    1. 如果玩家直接问某人（提到名字），那个人先回答
    2. 如果上一个说话的是 Mikko，这次 Aino 先说（交替）
    3. 如果上一个说话的是 Aino，这次 Mikko 先说
    4. 默认 Mikko 先说
    5. 有时只返回一个人（随机性）
    """
    import random
    
    user_lower = user_content.lower()
    
    # 规则1: 玩家直接问某人
    if "mikko" in user_lower or "米科" in user_lower:
        first = "mikko"
    elif "aino" in user_lower or "艾诺" in user_lower:
        first = "aino"
    else:
        # 规则2/3: 交替发言
        last_speaker = None
        for msg in reversed(messages):
            if msg.get("role") == "model" and msg.get("name") in ["Mikko", "Aino"]:
                last_speaker = msg["name"].lower()
                break
        
        if last_speaker == "mikko":
            first = "aino"
        elif last_speaker == "aino":
            first = "mikko"
        else:
            first = "mikko"  # 默认
    
    second = "aino" if first == "mikko" else "mikko"
    
    # 随机性：30% 概率只有一人发言
    if random.random() < 0.3:
        return [first]
    
    return [first, second]


async def _finnish_students_respond(
    conversation_id: str,
    user_content: str,
    messages: list[dict],
    dynamic_personas_map: dict[str, DynamicPersona] | None = None
) -> str:
    """两个芬兰学生轮流响应玩家。

    Args:
        conversation_id: 会话 ID
        user_content: 用户消息
        messages: 消息列表
        dynamic_personas_map: 动态 persona 映射表（可选）
    """
    if dynamic_personas_map is None:
        dynamic_personas_map = {}

    speaker_order = _decide_speaker_order(messages, user_content)

    replies = []
    history_text = _format_conversation_history(messages)

    for persona_id in speaker_order:
        other_name = "Aino" if persona_id == "mikko" else "Mikko"

        # 获取 persona 名称（优先使用动态 persona）
        if persona_id in dynamic_personas_map:
            persona_name = dynamic_personas_map[persona_id].name
        else:
            persona_name = personas.PERSONAS[persona_id]["name"]

        # 构建提示：包含对话历史和上下文
        prompt_parts = []

        # 添加对话历史
        if history_text:
            prompt_parts.append(f"【对话记录】\n{history_text}")

        # 如果这是第二个发言者，告诉他前一个人刚说了什么
        if replies:
            prompt_parts.append(f"（{other_name} 刚刚说：{replies[-1]}）")

        prompt_parts.append(f"玩家说：{user_content}")
        prompt_parts.append("请自然地回应，1-2句话即可。")

        prompt = "\n\n".join(prompt_parts)

        # 获取动态 persona（如果有）
        dynamic_persona = dynamic_personas_map.get(persona_id)
        reply = await _call_agent(conversation_id, persona_id, prompt, messages, dynamic_persona)
        if reply:
            # 带上名字前缀
            replies.append(f"{persona_name}: {reply}")

    return "\n\n".join(replies) if replies else "（Mikko 和 Aino 暂时不知道说什么）"


async def _expert_respond(
    conversation_id: str,
    user_content: str,
    messages: list[dict],
    expert_id: str,
    expert_display_name: str,
    dynamic_personas_map: dict[str, DynamicPersona] | None = None,
) -> str:
    """Expert 附身模式：专家以角色身份回应玩家。

    Args:
        conversation_id: 会话 ID
        user_content: 玩家消息
        messages: 对话历史
        expert_id: 专家 persona ID（如 "religion_expert"）
        expert_display_name: 显示名称（如 "Mikko"）
        dynamic_personas_map: 动态 persona 映射表（可选）

    Returns:
        专家的回复（带名字前缀）
    """
    if dynamic_personas_map is None:
        dynamic_personas_map = {}

    history_text = _format_conversation_history(messages)

    prompt_parts = []
    if history_text:
        prompt_parts.append(f"【对话记录】\n{history_text}")

    prompt_parts.append(f"玩家说：{user_content}")
    prompt_parts.append("请用你的专业知识回应，2-3句话即可。")

    prompt = "\n\n".join(prompt_parts)

    # 检查是否有对应的动态 persona（用于角色附身时的性格特征）
    dynamic_persona = dynamic_personas_map.get(expert_display_name.lower())

    # 调用专家 Agent
    reply = await _call_agent(conversation_id, expert_id, prompt, messages, dynamic_persona)

    if reply:
        # 检查是否包含 [DONE] 标记（专家认为讨论完成）
        if "[DONE]" in reply:
            reply = reply.replace("[DONE]", "").strip()
            # 标记讨论完成（通过返回特殊格式让调用者处理）
        # 返回带名字的回复
        return f"{expert_display_name}: {reply}"

    return f"（{expert_display_name} 正在思考...）"


async def _call_observer(conversation_id: str, messages: list[dict]) -> str:
    """调用 Observer 生成总结。"""
    runner = personas.RUNNERS["observer"]
    app_name = "persona_observer"
    session_id = _session_id("observer", conversation_id)
    persona_name = personas.PERSONAS["observer"]["name"]

    await _get_or_create_session(runner, app_name, session_id)

    # 传入对话历史
    history_text = _format_conversation_history(messages)
    user_msg = f"【请总结以下对话】\n\n{history_text}"

    new_message = types.Content(role="user", parts=[types.Part(text=user_msg)])
    events = []
    async for evt in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=new_message
    ):
        events.append(evt)

    ai_reply = _get_reply_from_events(events)
    if ai_reply:
        messages.append({"role": "model", "name": persona_name, "content": ai_reply})
        return f"\n{persona_name}: {ai_reply}"

    return ""


async def _generate_group_initial_messages(
    persona_ids: list[str],
    conversation_id: str,
    dynamic_personas_map: dict[str, DynamicPersona] | None = None
) -> list[dict]:
    """生成群聊开场消息，返回 MessageItem 列表。

    Args:
        persona_ids: 角色 ID 列表
        conversation_id: 会话 ID
        dynamic_personas_map: 动态 persona 映射表（可选）
    """
    out: list[dict] = []

    if dynamic_personas_map is None:
        dynamic_personas_map = {}

    # 检查是否是芬兰学生组合（必须是恰好 ["mikko", "aino"] 或 ["aino", "mikko"]，无重复）
    is_finnish = (
        len(persona_ids) == 2 and
        set(persona_ids) == {"mikko", "aino"}
    )

    if is_finnish:
        # 两个独立 Agent 轮流生成开场对话
        # Mikko 先开口
        mikko_prompt = """【场景开始】你和好朋友 Aino 正在讨论今晚聚餐的准备。

请自然地开口打招呼或提起话题，就像朋友间的日常聊天：
- 话题可以是人数、地点、时间等
- 适当使用芬兰语词：Moi, No niin, Selvä
- 1-2句话即可，保持轻松

示例：
Moi! 今晚聚餐的事情准备得怎么样了？
"""
        mikko_dynamic = dynamic_personas_map.get("mikko")
        mikko_reply = await _call_agent(conversation_id, "mikko", mikko_prompt, out, mikko_dynamic)

        # Aino 回应 Mikko
        if mikko_reply:
            aino_prompt = f"""【场景开始】你和好朋友 Mikko 正在讨论今晚聚餐的准备。

Mikko 刚刚说：{mikko_reply}

请自然地回应他，就像朋友间的日常聊天：
- 可以回应他的话题，或者补充新的想法
- 适当使用芬兰语词：Kiitos, Selvä, Ehkä
- 1-2句话即可

示例：
Selvä! 人数大概定了吗？我在想饮食方面有没有需要注意的。
"""
            aino_dynamic = dynamic_personas_map.get("aino")
            await _call_agent(conversation_id, "aino", aino_prompt, out, aino_dynamic)
    else:
        # 通用开场（兼容其他 persona 和动态 persona）
        names = []
        for pid in persona_ids:
            if pid in dynamic_personas_map:
                names.append(dynamic_personas_map[pid].name)
            elif pid in personas.PERSONAS:
                names.append(personas.PERSONAS[pid]["name"])

        for pid in persona_ids:
            # 如果是动态 persona，使用动态配置
            if pid in dynamic_personas_map:
                dp = dynamic_personas_map[pid]
                runner = personas.RUNNERS.get("_dynamic_template")  # 使用通用 runner
                if runner is None:
                    # 如果没有通用 runner，使用 mikko 的 runner 作为模板
                    runner = personas.RUNNERS["mikko"]

                app_name = f"persona_{pid}"
                session_id = _session_id(pid, conversation_id)
                persona_name = dp.name

                await _get_or_create_session(runner, app_name, session_id)

                group_context = f"【群聊模式】现在有 {len(persona_ids)} 位角色在对话：{', '.join(names)}。"
                group_context += f"你是 {persona_name}，请以你的角色身份开始对话。"

                # 添加动态 persona 指令
                dynamic_instruction = _generate_dynamic_persona_instruction(dp)
                group_context = f"{dynamic_instruction}\n\n{group_context}"

                new_message = types.Content(role="user", parts=[types.Part(text=group_context)])
                events = []
                async for evt in runner.run_async(
                    user_id=USER_ID, session_id=session_id, new_message=new_message
                ):
                    events.append(evt)
                ai_reply = _get_reply_from_events(events)
                if ai_reply:
                    out.append({"role": "model", "name": persona_name, "content": ai_reply})

            # 如果是预定义 persona
            elif pid in personas.PERSONAS:
                runner = personas.RUNNERS[pid]
                app_name = f"persona_{pid}"
                session_id = _session_id(pid, conversation_id)
                persona_name = personas.PERSONAS[pid]["name"]
                await _get_or_create_session(runner, app_name, session_id)
                group_context = f"【群聊模式】现在有 {len(persona_ids)} 位角色在对话：{', '.join(names)}。"
                group_context += f"你是 {persona_name}，请以你的角色身份开始对话。"
                new_message = types.Content(role="user", parts=[types.Part(text=group_context)])
                events = []
                async for evt in runner.run_async(
                    user_id=USER_ID, session_id=session_id, new_message=new_message
                ):
                    events.append(evt)
                ai_reply = _get_reply_from_events(events)
                if ai_reply:
                    out.append({"role": "model", "name": persona_name, "content": ai_reply})

    return out


@app.get("/personas", response_model=list[PersonaItem])
def list_personas():
    """返回可选聊天对象列表，供 Godot 做下拉/按钮切换。"""
    return [
        PersonaItem(id=pid, name=info["name"])
        for pid, info in personas.PERSONAS.items()
    ]


# ---------- RESTful: 会话与消息 ----------


@app.post("/conversations", response_model=ConversationItem)
async def create_conversation(req: CreateConversationReq):
    """创建会话（单人或群聊）。芬兰学生讨论组会自动生成开场对话。

    支持动态 persona：通过 dynamic_personas 参数传入角色配置，无需修改后端代码。
    """
    persona_ids = [p.strip().lower() for p in req.persona_ids if p.strip()]
    if not persona_ids:
        persona_ids = DEFAULT_PERSONAS.copy()  # 默认使用芬兰学生双人组合

    # 检测重复的 persona ID
    seen = set()
    duplicates = []
    for pid in persona_ids:
        if pid in seen:
            duplicates.append(pid)
        seen.add(pid)
    if duplicates:
        # 统计每个重复 ID 的出现次数
        from collections import Counter
        counts = Counter(persona_ids)
        dup_details = ", ".join(f"{pid} 出现了 {counts[pid]} 次" for pid in set(duplicates))
        raise HTTPException(
            400,
            detail=f"检测到重复的聊天对象: {dup_details}",
        )

    # 创建动态 persona 映射表
    dynamic_personas_map: dict[str, DynamicPersona] = {}
    for dp in req.dynamic_personas:
        dynamic_personas_map[dp.id] = dp

    # 验证 persona IDs：要么在预定义列表中，要么在动态 persona 中
    invalid = []
    for p in persona_ids:
        if p not in personas.PERSONAS and p not in dynamic_personas_map:
            invalid.append(p)

    if invalid:
        available = list(personas.PERSONAS.keys()) + list(dynamic_personas_map.keys())
        raise HTTPException(
            400,
            detail=f"未知的聊天对象: {', '.join(invalid)}，可用: {', '.join(available)}。",
        )

    conv_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    CONVERSATIONS[conv_id] = {
        "persona_ids": persona_ids,
        "messages": [],
        "created_at": now,
        "dynamic_personas": req.dynamic_personas,  # 保存动态 persona 配置
    }

    # 芬兰学生讨论组或多人群聊时生成开场对话
    is_finnish_pair = len(persona_ids) == 2 and set(persona_ids) == {"mikko", "aino"}
    if len(persona_ids) >= 2 or is_finnish_pair:
        try:
            initial = await _generate_group_initial_messages(
                persona_ids,
                conv_id,
                dynamic_personas_map
            )
            CONVERSATIONS[conv_id]["messages"] = initial
        except Exception as e:
            print(f"[WARNING] 生成开场对话失败: {e}")
            # 使用默认开场白
            CONVERSATIONS[conv_id]["messages"] = [
                {"role": "model", "name": "Mikko", "content": "Moi! 今晚聚餐准备得怎么样了？"},
                {"role": "model", "name": "Aino", "content": "Selvä! 我们正在讨论细节呢。"}
            ]
    msgs = CONVERSATIONS[conv_id]["messages"]
    return ConversationItem(
        id=conv_id,
        persona_ids=persona_ids,
        messages=[MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in msgs],
        created_at=now,
    )


@app.get("/conversations", response_model=list[ConversationSummary])
def list_conversations():
    """返回会话列表（摘要），不含 default_ 兼容会话。"""
    out = []
    for cid, c in CONVERSATIONS.items():
        if cid.startswith("default_"):
            continue
        out.append(
            ConversationSummary(
                id=cid,
                persona_ids=c["persona_ids"],
                created_at=c["created_at"],
                message_count=len(c["messages"]),
            )
        )
    out.sort(key=lambda x: x.created_at, reverse=True)
    return out


@app.get("/conversations/{conversation_id}", response_model=ConversationItem)
def get_conversation(conversation_id: str):
    """获取单个会话详情（含消息历史）。"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="会话不存在")
    msgs = c["messages"]
    return ConversationItem(
        id=conversation_id,
        persona_ids=c["persona_ids"],
        messages=[MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in msgs],
        created_at=c["created_at"],
    )


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, limit: int | None = None, offset: int = 0):
    """获取会话消息列表，支持 limit/offset 分页。"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="会话不存在")
    msgs = c["messages"]
    total = len(msgs)
    if offset > 0 or (limit is not None and limit < total):
        msgs = msgs[offset : (offset + limit) if limit is not None else None]
    return {
        "messages": [MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in msgs],
        "total": total,
    }


@app.get("/conversations/{conversation_id}/summary")
async def get_conversation_summary(conversation_id: str):
    """获取 Observer 对话总结。"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="会话不存在")

    # 调用 Observer 生成总结
    messages = c["messages"]
    summary = await _call_observer(conversation_id, messages)

    return {
        "conversation_id": conversation_id,
        "summary": summary,
        "messages_count": len(messages),
        "phase": CONVERSATION_STATES.get(conversation_id, {}).get("phase", "unknown")
    }


@app.post("/conversations/{conversation_id}/messages")
async def post_conversation_message(conversation_id: str, req: PostMessageReq):
    """在会话中发送一条消息，返回本轮新增的消息及合并回复。"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="会话不存在")
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(400, detail="消息内容不能为空")
    prev_len = len(c["messages"])
    try:
        combined = await _run_chat_round(conversation_id, c["persona_ids"], content)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    new_msgs = c["messages"][prev_len:]
    return {
        "messages": [MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in new_msgs],
        "reply": combined,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
