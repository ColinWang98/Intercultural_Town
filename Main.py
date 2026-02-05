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
DEFAULT_PERSONA = "french_student_male"

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
    """在指定会话中追加用户消息，调用 ADK 生成回复并追加到会话，返回合并后的回复文本。"""
    conv = CONVERSATIONS.get(conversation_id)
    if not conv:
        raise ValueError(f"conversation not found: {conversation_id}")
    messages = conv["messages"]
    messages.append({"role": "user", "name": None, "content": user_content})

    persona_names = [personas.PERSONAS[pid]["name"] for pid in persona_ids]
    history_text = _format_conversation_history(messages)

    replies: list[str] = []
    for idx, pid in enumerate(persona_ids):
        runner = personas.RUNNERS[pid]
        app_name = f"persona_{pid}"
        session_id = _session_id(pid, conversation_id)
        persona_name = persona_names[idx]
        await _get_or_create_session(runner, app_name, session_id)

        if len(persona_ids) > 1:
            group_context = (
                f"【群聊模式】现在有 {len(persona_ids)} 位角色在对话：{', '.join(persona_names)}。\n"
            )
            if history_text:
                group_context += "下面是对话记录，请在该上下文中继续对话：\n"
                group_context += history_text + "\n\n"
            group_context += f"你是 {persona_name}，请以你的角色身份参与对话。【协作规则】如果你不确定答案或需要他人意见，可以使用 ask_agent 工具询问其他角色。"
            user_msg = group_context
        else:
            user_msg = user_content

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
            replies.append(f"[{persona_name}] {ai_reply}")
            messages.append({"role": "model", "name": persona_name, "content": ai_reply})

    if not replies:
        return "（大家都没想出要说啥，再说一句试试？）"
    return "\n\n".join(replies)


async def _generate_group_initial_messages(persona_ids: list[str], conversation_id: str) -> list[dict]:
    """生成群聊开场消息（法国学生特殊逻辑或通用开场），返回 MessageItem 列表。"""
    is_french = (
        len(persona_ids) == 2
        and "french_student_male" in persona_ids
        and "french_student_female" in persona_ids
    )
    initial_prompt_fr = """Vous discutez de la préparation de la soirée de ce soir.
Parlez de la nourriture à préparer (quels plats, qui apporte quoi),
de la décoration et de la disposition de la salle,
et de qui va s'occuper de quoi.
Commencez la conversation naturellement."""
    out: list[dict] = []
    if is_french:
        male_runner = personas.RUNNERS["french_student_male"]
        male_app = "persona_french_student_male"
        male_session = _session_id("french_student_male", conversation_id)
        await _get_or_create_session(male_runner, male_app, male_session)
        male_msg = f"【场景】你和另一位法国女学生正在讨论今晚 party 的准备。\n\n{initial_prompt_fr}\n\n请用中文回复，可适当夹杂法语词。"
        male_content = types.Content(role="user", parts=[types.Part(text=male_msg)])
        male_events = []
        async for evt in male_runner.run_async(
            user_id=USER_ID, session_id=male_session, new_message=male_content
        ):
            male_events.append(evt)
        male_reply = _get_reply_from_events(male_events)
        male_name = personas.PERSONAS["french_student_male"]["name"]
        if male_reply:
            out.append({"role": "model", "name": male_name, "content": male_reply})
        female_runner = personas.RUNNERS["french_student_female"]
        female_app = "persona_french_student_female"
        female_session = _session_id("french_student_female", conversation_id)
        await _get_or_create_session(female_runner, female_app, female_session)
        female_context = f"【场景】你和另一位法国男学生正在讨论今晚 party 的准备。\n\n{initial_prompt_fr}\n\n"
        if male_reply:
            female_context += f"对方说：{male_reply}\n\n请用中文回复，可适当夹杂法语词，回应对方并继续讨论。"
        else:
            female_context += "请用中文回复，可适当夹杂法语词，开始讨论。"
        female_content = types.Content(role="user", parts=[types.Part(text=female_context)])
        female_events = []
        async for evt in female_runner.run_async(
            user_id=USER_ID, session_id=female_session, new_message=female_content
        ):
            female_events.append(evt)
        female_reply = _get_reply_from_events(female_events)
        female_name = personas.PERSONAS["french_student_female"]["name"]
        if female_reply:
            out.append({"role": "model", "name": female_name, "content": female_reply})
    else:
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
    """创建会话（单人或群聊）。群聊且为两位法国学生时会自动生成开场对话。"""
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
    if len(persona_ids) >= 2:
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
