import re
import uuid
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.genai import types

import personas

# 多 persona：每个角色独立 session，切换即切换聊天对象
USER_ID = "godot"
DEFAULT_PERSONA = "finnish_discussion_root"

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
class CreateConversationReq(BaseModel):
    persona_ids: list[str]


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


# 会话存储：id -> { persona_ids, messages, created_at }
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

def _strip_thinking(text: str) -> str:
    """尽量移除模型输出中的“思考过程”片段（如 <think>...</think>，含大小写变体）。"""
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
    # 去掉以“思考：”“（思考）”“推理：”等开头的整行
    lines = text.split("\n")
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith(("思考：", "（思考）", "推理：", "【思考】", "（推理）")):
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


def _detect_focus_flags(messages: list[dict]) -> tuple[bool, bool]:
    """扫描玩家消息，判断是否提到宗教/过敏相关话题。

    Returns:
        (has_religion_focus, has_allergy_focus)
    """
    religion_keywords = ["宗教", "清真", "穆斯林", "犹太", "洁食", "halal", "kosher", "斋月", "素食", "纯素"]
    allergy_keywords = ["过敏", "花生", "坚果", "海鲜", "乳糖", "奶制品", "麸质", "gluten"]

    has_religion_focus = False
    has_allergy_focus = False

    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "").lower()
            if any(kw in content for kw in religion_keywords):
                has_religion_focus = True
            if any(kw in content for kw in allergy_keywords):
                has_allergy_focus = True

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

    # 获取当前状态
    phase = state["phase"]

    # === 状态机逻辑 ===
    if phase == "small_talk":
        # 检测关键词
        has_religion, has_allergy = _detect_focus_flags(messages)

        if has_religion and not state["religion_discussed"]:
            state["phase"] = "religion_deep"
            state["sub_agent_turns"] = 0
            print(f"[STATE] {conversation_id}: small_talk -> religion_deep")
        elif has_allergy and not state["allergy_discussed"]:
            state["phase"] = "allergy_deep"
            state["sub_agent_turns"] = 0
            print(f"[STATE] {conversation_id}: small_talk -> allergy_deep")
        elif state["religion_discussed"] and state["allergy_discussed"]:
            state["phase"] = "wrap_up"
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
        # ROOT Agent 闲聊
        return await _call_root_agent(conversation_id, "finnish_discussion_root", user_content, messages)
    elif phase == "religion_deep":
        # 宗教专家主导
        return await _call_root_agent(conversation_id, "finnish_discussion_root", user_content, messages)
    elif phase == "allergy_deep":
        # 过敏专家主导
        return await _call_root_agent(conversation_id, "finnish_discussion_root", user_content, messages)
    elif phase == "wrap_up":
        # ROOT Agent 收尾
        reply = await _call_root_agent(conversation_id, "finnish_discussion_root", user_content, messages)
        # 如果已进入 finished，调用 Observer
        if state["phase"] == "finished":
            observer_reply = await _call_observer(conversation_id, messages)
            return f"{reply}\n\n{observer_reply}"
        return reply
    elif phase == "finished":
        # 已完成，只返回 Observer 总结
        return await _call_observer(conversation_id, messages)

    return "（对话状态异常，请重启会话）"


async def _call_root_agent(conversation_id: str, persona_id: str, user_content: str, messages: list[dict]) -> str:
    """调用 ROOT Agent（芬兰学生讨论组）。"""
    runner = personas.RUNNERS[persona_id]
    app_name = f"persona_{persona_id}"
    session_id = _session_id(persona_id, conversation_id)
    persona_name = personas.PERSONAS[persona_id]["name"]

    await _get_or_create_session(runner, app_name, session_id)

    # 传入对话历史
    history_text = _format_conversation_history(messages)
    user_msg = f"{user_content}\n\n【对话记录】\n{history_text}" if history_text else user_content

    new_message = types.Content(role="user", parts=[types.Part(text=user_msg)])
    events = []
    async for evt in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=new_message
    ):
        events.append(evt)

        # Log tool call events
        if hasattr(evt, 'content') and evt.content:
            if hasattr(evt.content, 'parts'):
                for part in evt.content.parts or []:
                    if hasattr(part, 'function_call'):
                        print(f"[TOOL CALL] {persona_name} -> {part.function_call.name}({part.function_call.args})")
                    elif hasattr(part, 'function_response'):
                        print(f"[TOOL RESULT] {persona_name} <- {part.function_response.response}")

    ai_reply = _get_reply_from_events(events)
    if ai_reply:
        messages.append({"role": "model", "name": persona_name, "content": ai_reply})
        return ai_reply

    return "（Mikko 和 Aino 暂时不知道说什么）"


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
        return f"\n【{persona_name}】\n{ai_reply}"

    return ""


async def _generate_group_initial_messages(persona_ids: list[str], conversation_id: str) -> list[dict]:
    """生成群聊开场消息，返回 MessageItem 列表。"""
    out: list[dict] = []

    # 检查是否是芬兰学生讨论组
    is_finnish = "finnish_discussion_root" in persona_ids

    if is_finnish:
        # ROOT Agent 生成开场对话（同时扮演 Mikko 和 Aino）
        runner = personas.RUNNERS["finnish_discussion_root"]
        app_name = "persona_finnish_discussion_root"
        session_id = _session_id("finnish_discussion_root", conversation_id)
        persona_name = personas.PERSONAS["finnish_discussion_root"]["name"]

        await _get_or_create_session(runner, app_name, session_id)

        # 开场提示
        initial_prompt = """【场景】你们是两个芬兰学生 Mikko 和 Aino，正在讨论今晚聚餐的准备。
话题包括：人数、地点、时间、气氛等轻松话题。

请以你们两个的口吻开始对话，格式如下：
Mikko: [Mikko 说的话]
Aino: [Aino 说的话]

注意：
- 每次回复 2-3 句话，不要信息轰炸
- 适当夹杂芬兰语词：Moi, Kiitos, No niin, Selvä
- 保持轻松愉快的氛围
"""

        new_message = types.Content(role="user", parts=[types.Part(text=initial_prompt)])
        events = []
        async for evt in runner.run_async(
            user_id=USER_ID, session_id=session_id, new_message=new_message
        ):
            events.append(evt)

        ai_reply = _get_reply_from_events(events)
        if ai_reply:
            out.append({"role": "model", "name": persona_name, "content": ai_reply})
    else:
        # 通用开场（兼容其他 persona）
        names = [personas.PERSONAS[pid]["name"] for pid in persona_ids]
        for pid in persona_ids:
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
    """创建会话（单人或群聊）。芬兰学生讨论组会自动生成开场对话。"""
    persona_ids = [p.strip().lower() for p in req.persona_ids if p.strip()]
    if not persona_ids:
        persona_ids = [DEFAULT_PERSONA]
    invalid = [p for p in persona_ids if p not in personas.PERSONAS]
    if invalid:
        raise HTTPException(
            400,
            detail=f"未知的聊天对象: {', '.join(invalid)}，可用: {', '.join(personas.PERSONAS)}。",
        )
    conv_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    CONVERSATIONS[conv_id] = {
        "persona_ids": persona_ids,
        "messages": [],
        "created_at": now,
    }
    # 芬兰学生讨论组或多人群聊时生成开场对话
    if len(persona_ids) >= 2 or "finnish_discussion_root" in persona_ids:
        initial = await _generate_group_initial_messages(persona_ids, conv_id)
        CONVERSATIONS[conv_id]["messages"] = initial
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
