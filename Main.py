import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.genai import types

# * import personas *
from dotenv import load_dotenv
load_dotenv()  # * .env *

import personas  # *

# * persona* session*
USER_ID = "godot"
DEFAULT_PERSONAS = ["mikko", "aino"]  # *


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    provider = "Azure OpenAI" if personas.USE_AZURE else "本地 Ollama"
    print(f"[Startup] 模型提供商: {provider}")
    print(f"[Startup] 可用 personas: {', '.join(personas.PERSONAS.keys())}")
    yield
    # 关闭时执行（如果需要）
    print("[Shutdown] 应用关闭")


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    """*/* 404*"""
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
    """* favicon * 404*"""
    from fastapi.responses import Response
    return Response(status_code=204)


class PersonaItem(BaseModel):
    id: str
    name: str


# ---------- RESTful: * ----------

class DynamicPersona(BaseModel):
    """* Persona * Godot *"""
    id: str
    name: str
    gender: str = "Male"  # *Male, Female, Non-binary, Other
    nationality: str = ""  # * Finnish, Chinese, American*
    major: str = ""  # */* Computer Science, Psychology*
    personality: str = ""  # *
    personality_type: str = "Extrovert"  # Extrovert, Introvert, Ambivert
    interests: str = ""  # *
    speaking_style: str = ""  # *
    likes: List[str] = []  # *
    dislikes: List[str] = []  # *
    current_state: str = ""  # *
    location_hint: str = ""  # *

    # * Analyser *
    # * dynamic_persona *
    event_title: str = ""  # *"*student hall*party"*
    event_description: str = ""  # *"*"*
    event_topics: List[str] = []  # *["*", "*", "*"]*
    required_topics: List[str] = []  # *["*"]*


class CreateConversationReq(BaseModel):
    persona_ids: List[str]
    dynamic_personas: List[DynamicPersona] = []  # * persona *
    player_name: Optional[str] = None  # 玩家名称


class PostMessageReq(BaseModel):
    content: str
    persona_id: Optional[str] = None  # * persona_id *
    player_name: Optional[str] = None  # *


# *role=user * name *role=model *
class MessageItem(BaseModel):
    role: str  # "user" | "model"
    name: Optional[str] = None
    content: str


class ConversationItem(BaseModel):
    id: str
    persona_ids: List[str]
    messages: List[MessageItem]
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    persona_ids: List[str]
    created_at: str
    message_count: int


# *id -> { persona_ids, messages, created_at, dynamic_personas }
CONVERSATIONS: Dict[str, Dict] = {}

# *id -> {
#     "phase": "small_talk" | "finished",
# }
CONVERSATION_STATES: Dict[str, Dict] = {}

# */* Godot *
MAX_REPLY_LENGTH = 2000


def _format_conversation_history(messages: List[dict]) -> str:
    """*: / *: *

    【重要】使用方括号 [] 格式化名字，避免 AI 在输出时模仿 "名字：" 格式
    """
    lines: List[str] = []
    for m in messages:
        role, name, content = m.get("role"), m.get("name"), m.get("content", "")
        if role == "user":
            # Player 消息
            lines.append(f"Player says: {content}")
        elif role == "model" and name:
            # Agent 消息 -> 格式（AI 不容易模仿）
            lines.append(f"{name} says: {content}")
        elif content:
            lines.append(content)
    return "\n".join(lines)


def _generate_dynamic_persona_instruction(dynamic_persona: DynamicPersona) -> str:
    """* persona * AI *"""
    # *
    gender_map = {
        "Male": "*",
        "Female": "*",
        "Non-binary": "*",
        "Other": "*"
    }
    gender_text = gender_map.get(dynamic_persona.gender, dynamic_persona.gender)

    # *
    personality_type_map = {
        "Extrovert": "*",
        "Introvert": "*",
        "Ambivert": "*"
    }
    personality_type_text = personality_type_map.get(dynamic_persona.personality_type, dynamic_persona.personality_type)

    # *
    identity_parts = [f"* **{dynamic_persona.name}**"]
    if dynamic_persona.nationality:
        identity_parts.append(f"* {dynamic_persona.nationality}")
    identity_parts.append(f"{gender_text}")
    if dynamic_persona.major:
        identity_parts.append(f"* {dynamic_persona.major}")
    
    instruction = "*".join(identity_parts) + "*\n\n"

    # *
    if dynamic_persona.gender == "Male":
        instruction += "*\n"
    elif dynamic_persona.gender == "Female":
        instruction += "*\n"

    # *
    if dynamic_persona.nationality:
        instruction += f"* {dynamic_persona.nationality} *\n"
    if dynamic_persona.major:
        instruction += f"* {dynamic_persona.major} *\n"

    # * nationality * - 让 AI 根据国籍自然生成口头禅
    if dynamic_persona.nationality:
        instruction += f"""
******口头禅使用：⚠️ 重要！
你是 {dynamic_persona.nationality}，请根据该语言/文化的特点，**自然地、偶尔地**使用符合该国籍的常见口头禅和问候语。

例如：
- 如果是 Finnish（芬兰），可以自然使用：Moi (你好), Kiitos (谢谢), No niin (好了), Selvä (明白), Ehkä (也许) 等
- 如果是 Chinese（中国），可以自然使用：你好, 谢谢, 好的, 行, 可能吧 等
- 如果是 American（美国），可以自然使用：Hi/Hello, Thanks, Okay/Sure, Maybe 等
- 如果是 Japanese（日本），可以自然使用：こんにちは, ありがとう, はい/わかった, たぶん 等

⚠️ 关键要求：
1. **偶尔使用**：不要每句话都加口头禅，保持自然
2. **符合语境**：根据对话场景选择合适的表达
3. **不要过度**：不要为了展示口头禅而刻意堆砌
4. **自然流畅**：让口头禅成为你说话风格的有机部分
"""

    # *
    if dynamic_persona.personality:
        instruction += f"\n******{dynamic_persona.personality}\n"
    else:
        instruction += f"\n******{personality_type_text}\n"

    # *
    if dynamic_persona.interests:
        instruction += f"******{dynamic_persona.interests}\n"

    # *
    if dynamic_persona.speaking_style:
        instruction += f"******{dynamic_persona.speaking_style}\n"

    # *
    if dynamic_persona.likes:
        instruction += f"******{', '.join(dynamic_persona.likes)}\n"

    # *
    if dynamic_persona.dislikes:
        print(f"[Backend] * {dynamic_persona.name} * dislikes: {dynamic_persona.dislikes}")
        instruction += f"******{', '.join(dynamic_persona.dislikes)}\n"

    # *
    if dynamic_persona.current_state:
        instruction += f"\n******{dynamic_persona.current_state}\n"

    # *
    if dynamic_persona.location_hint:
        instruction += f"******{dynamic_persona.location_hint}\n"

    instruction += "\n*"

    return instruction

def _strip_thinking(text: str) -> str:
    """*"*"* <think>...</think>*"""
    if not text:
        return text
    # DeepSeek R1 * <think>/</think> *
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # * <think>*
    match = re.search(r"<think>", text, re.IGNORECASE)
    if match:
        text = text[: match.start()]
    
    # * "Mikko:", "Aino:", *
    # * "*:" * "*" *
    dialogue_patterns = [
        r"^(Mikko|Aino|\*|Observer)\s*[:*]",  # "Mikko:" "Aino:" *
        r"^\*(Mikko|Aino|\*|Observer)\*",       # *Mikko*
    ]
    
    lines = text.split("\n")
    dialogue_start_idx = None
    
    # *
    for i, line in enumerate(lines):
        s = line.strip()
        for pattern in dialogue_patterns:
            if re.match(pattern, s, re.IGNORECASE):
                dialogue_start_idx = i
                break
        if dialogue_start_idx is not None:
            break
    
    # *
    if dialogue_start_idx is not None:
        lines = lines[dialogue_start_idx:]
        return "\n".join(lines).strip()
    
    # *
    # *
    thinking_prefixes = (
        "*", "*", "*", "*", "*",
        "*", "*", "*", "OK*", "Ok*", "ok*",
        "*", "*", "*", "*",
        "*", "*", "*", "*", "*",
        "*", "*", "*", "*",
        "*", "*", "*", "*", "*",
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
    """* ADK * events * model *
    *
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
            # *
            if text in seen:
                continue
            seen.add(text)
            parts.append(text)
    reply = _strip_thinking("".join(parts).strip()) or None
    if reply and len(reply) > MAX_REPLY_LENGTH:
        reply = reply[:MAX_REPLY_LENGTH].rstrip() + "..."
    return reply


def _session_id(persona_id: str, conversation_id: Optional[str] = None) -> str:
    """ADK * id* conversation_id* persona *"""
    if conversation_id:
        return conversation_id
    return f"default_{persona_id}"


async def _get_or_create_session(runner, app_name: str, session_id: str):
    """* persona * session*"""
    try:
        session = await runner.session_service.get_session(
            app_name=app_name, user_id=USER_ID, session_id=session_id
        )
        if session is None:
            print(f"[Session] * session: {app_name}/{session_id}")
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=USER_ID, session_id=session_id
            )
        else:
            print(f"[Session] * session: {app_name}/{session_id}")
        return session
    except Exception as e:
        print(f"[Session] * session *: {e}* session")
        # *
        session = await runner.session_service.create_session(
            app_name=app_name, user_id=USER_ID, session_id=session_id
        )
        return session


async def _run_chat_round(conversation_id: str, persona_ids: List[str], user_content: str, player_name: Optional[str] = None) -> str:
    """* ADK *

    *
    - small_talk: *
    - religion_deep: *
    - allergy_deep: *
    - wrap_up: *
    - finished: * Observer

    * persona* dynamic_personas *
    """
    conv = CONVERSATIONS.get(conversation_id)
    if not conv:
        raise ValueError(f"conversation not found: {conversation_id}")

    # *
    if conversation_id not in CONVERSATION_STATES:
        CONVERSATION_STATES[conversation_id] = {
            "phase": "small_talk",
        }

    state = CONVERSATION_STATES[conversation_id]
    messages = conv["messages"]
    messages.append({"role": "user", "name": player_name, "content": user_content})

    # * persona *
    dynamic_personas_list = conv.get("dynamic_personas", [])
    dynamic_personas_map: Dict[str, DynamicPersona] = {
        dp.id: dp for dp in dynamic_personas_list
    }
    
    # *
    event_context = conv.get("event_context")

    # *
    phase = state["phase"]

    # === * ===
    if phase == "small_talk":
        # *
        user_lower = user_content.lower()
        end_words = ["*", "*", "*", "*", "*", "*"]
        if any(word in user_lower for word in end_words):
            state["phase"] = "evaluation"
            phase = "evaluation"
            print(f"[STATE] {conversation_id}: small_talk -> evaluation")

    # === * Agent ===
    if phase == "small_talk":
        # * persona* persona_ids*
        reply = await _finnish_students_respond(
            conversation_id,
            user_content,
            messages,
            dynamic_personas_map,
            persona_ids,  # * persona_ids
            event_context,  # *
            player_name  # *
        )

        # *
        # * 2 * agent * 1 *
        user_message_count = sum(1 for m in messages if m.get("role") == "user")
        
        # * 5* emoji *
        if user_message_count == 5:
            print(f"[Analyser] * {user_message_count} * (emoji)")
            evaluation = await _call_analyser(conversation_id, messages, conv.get("event_context"), round_number=5)
            
            # * emoji
            emoji_reply = ""
            if evaluation.get("emoji_suggestion"):
                emoji_data = evaluation["emoji_suggestion"]
                mood = emoji_data.get("mood", "happy")
                emojis = emoji_data.get("emojis", [])
                
                if emojis:
                    emoji_str = "".join(emojis)
                    print(f"[Analyser] *: mood={mood}, emojis={emoji_str}")
                    
                    # * emoji (agent *)
                    emoji_replies = []
                    for pid in persona_ids:
                        if pid in dynamic_personas_map or pid in personas.PERSONAS:
                            dynamic_persona = dynamic_personas_map.get(pid)
                            # * agent emoji
                            emoji_prompt = f"*[OK]* {emoji_str} *[OK]*"
                            agent_emoji = await _call_agent(conversation_id, pid, emoji_prompt, messages, dynamic_persona)
                            if agent_emoji:
                                emoji_replies.append(agent_emoji)
                    
                    if emoji_replies:
                        emoji_reply = "\n\n".join(emoji_replies)
                        return f"{reply}\n\n{emoji_reply}"
            
            # * intervention
            if evaluation.get("needs_intervention") and evaluation.get("intervention"):
                intervention = evaluation["intervention"]
                target_agents = intervention.get("target_agents", [])
                prompt = intervention.get("prompt", "")
                
                if target_agents and prompt:
                    print(f"[Analyser] *target_agents={target_agents}")
                    intervention_replies = []
                    for pid in target_agents:
                        if pid in dynamic_personas_map or pid in personas.PERSONAS:
                            dynamic_persona = dynamic_personas_map.get(pid)
                            agent_reply = await _call_agent(conversation_id, pid, prompt, messages, dynamic_persona)
                            if agent_reply:
                                intervention_replies.append(agent_reply)
                    
                    if intervention_replies:
                        intervention_reply = "\n\n".join(intervention_replies)
                        return f"{reply}\n\n{intervention_reply}"
        
        elif user_message_count >= 3 and user_message_count % 3 == 0:
            # *
            print(f"[Analyser] * {user_message_count} *")
            evaluation = await _call_analyser(conversation_id, messages, conv.get("event_context"))
            if evaluation.get("needs_intervention") and evaluation.get("intervention"):
                # *
                intervention = evaluation["intervention"]
                target_agents = intervention.get("target_agents", [])
                prompt = intervention.get("prompt", "")

                if target_agents and prompt:
                    print(f"[Analyser] *target_agents={target_agents}")
                    # * agent *
                    intervention_replies = []
                    for pid in target_agents:
                        if pid in dynamic_personas_map or pid in personas.PERSONAS:
                            dynamic_persona = dynamic_personas_map.get(pid)
                            agent_reply = await _call_agent(conversation_id, pid, prompt, messages, dynamic_persona)
                            if agent_reply:
                                intervention_replies.append(agent_reply)

                    if intervention_replies:
                        intervention_reply = "\n\n".join(intervention_replies)
                        return f"{reply}\n\n{intervention_reply}"

        return reply

    elif phase == "evaluation":
        # * Analyser *
        print(f"[Analyser] *")
        evaluation = await _call_analyser(conversation_id, messages, conv.get("event_context"))

        # * finished *
        state["phase"] = "finished"

        # *
        report_parts = []
        if evaluation.get("passed"):
            report_parts.append("[PASS] *")
        else:
            report_parts.append("[WARN] *")

        if evaluation.get("criteria"):
            criteria = evaluation["criteria"]
            report_parts.append("\n*")
            for key, value in criteria.items():
                status = "[OK]" if value.get("passed") else "[FAIL]"
                report_parts.append(f"{status} {key}: {value.get('score', 0)}/100")
                if value.get("reason"):
                    report_parts.append(f"   *{value['reason']}")

        if evaluation.get("issues"):
            report_parts.append("\n*")
            for issue in evaluation["issues"]:
                report_parts.append(f"- {issue}")

        if evaluation.get("suggestions"):
            report_parts.append("\n*")
            for suggestion in evaluation["suggestions"]:
                report_parts.append(f"- {suggestion}")

        # * Observer *
        observer_reply = await _call_observer(conversation_id, messages)

        # *
        final_reply = await _finnish_students_respond(conversation_id, user_content, messages, dynamic_personas_map, None, event_context)

        # *
        evaluation_report = "\n".join(report_parts)
        return f"{final_reply}\n\n{evaluation_report}\n\n{observer_reply}"

    elif phase == "finished":
        # * Observer *
        observer_reply = await _call_observer(conversation_id, messages)
        return observer_reply

    return "*"


async def _call_agent(
    conversation_id: str,
    persona_id: str,
    prompt: str,
    messages: List[dict],
    dynamic_persona: Optional[DynamicPersona] = None
) -> str:
    """调用 Agent 生成回复

    Args:
        conversation_id: 会话 ID
        persona_id: persona ID
        prompt: 提示内容
        messages: 消息历史
        dynamic_persona: 动态 persona（优先使用）
    """
    # 优先使用 dynamic_persona（如果有）
    if dynamic_persona:
        # 使用动态 persona 创建/获取 runner
        print(f"[INFO] 使用 dynamic persona: {persona_id} ({dynamic_persona.name})")
        instruction = _generate_dynamic_persona_instruction(dynamic_persona)
        runner = personas.create_dynamic_runner(
            persona_id=persona_id,
            name=dynamic_persona.name,
            instruction=instruction
        )
        app_name = f"persona_{persona_id}"
        persona_name = dynamic_persona.name
    elif persona_id in personas.RUNNERS:
        # 使用预定义 persona
        runner = personas.RUNNERS[persona_id]
        app_name = f"persona_{persona_id}"
        persona_name = personas.PERSONAS[persona_id]["name"]
    else:
        # 回退到 mikko
        print(f"[WARNING] persona_id '{persona_id}' 未找到，使用 mikko runner 作为回退")
        runner = personas.RUNNERS["mikko"]
        app_name = "persona_mikko"
        persona_name = personas.PERSONAS["mikko"]["name"]

    # session_id 使用 conversation_id 或默认值
    session_id = conversation_id if conversation_id else f"default_{persona_id}"

    # [SESSION] 创建或获取 session
    try:
        await _get_or_create_session(runner, app_name, session_id)
    except Exception as e:
        print(f"[WARNING] 创建/获取 session 失败: {e}")

    # * persona * Agent * instruction *
    # * create_dynamic_runner * instruction *

    new_message = types.Content(role="user", parts=[types.Part(text=prompt)])
    events = []
    try:
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
    except Exception as e:
        print(f"[ERROR] * agent {persona_name} *: {e}")
        import traceback
        traceback.print_exc()
        return ""

    ai_reply = _get_reply_from_events(events)
    if ai_reply:
        messages.append({"role": "model", "name": persona_name, "content": ai_reply})
        return ai_reply

    return ""


def _decide_speaker_order(
    persona_ids: List[str],
    messages: List[dict],
    user_content: str
) -> List[str]:
    """*

    Args:
        persona_ids: * persona_ids *
        messages: *
        user_content: *

    *
    1. *
    2. *
    3. * A* B *
    4. *
    5. *
    """
    import random

    # * persona_ids*
    valid_ids = [pid.lower() for pid in persona_ids if pid]

    if not valid_ids:
        return []

    # *
    if len(valid_ids) == 1:
        return [persona_ids[0]]

    user_lower = user_content.lower()

    # */* ID
    id_map = {}
    for pid in persona_ids:
        id_map[pid.lower()] = pid

    # *1: *
    first_lower = None
    for pid_lower in valid_ids:
        if pid_lower in user_lower:
            first_lower = pid_lower
            break

    if not first_lower:
        # *2/3: * - *
        last_speaker = None
        for msg in reversed(messages):
            name = msg.get("name", "").lower()
            for pid_lower in valid_ids:
                if pid_lower in name or name in pid_lower:
                    last_speaker = pid_lower
                    break
            if last_speaker:
                break

        if last_speaker:
            # *
            idx = valid_ids.index(last_speaker)
            next_idx = (idx + 1) % len(valid_ids)
            first_lower = valid_ids[next_idx]
        else:
            # *
            first_lower = valid_ids[0]

    first = id_map.get(first_lower, first_lower)

    # *
    result = [first]

    # *
    if len(valid_ids) > 1 and random.random() < 0.3:
        return result

    # *
    for pid_lower in valid_ids:
        pid = id_map.get(pid_lower, pid_lower)
        if pid != first:
            result.append(pid)

    return result


async def _finnish_students_respond(
    conversation_id: str,
    user_content: str,
    messages: List[dict],
    dynamic_personas_map: Optional[Dict[str, DynamicPersona]] = None,
    persona_ids: Optional[List[str]] = None,
    event_context: Optional[dict] = None,
    player_name: Optional[str] = None
) -> str:
    """* persona_ids * Agent *

    Args:
        conversation_id: * ID
        user_content: *
        messages: *
        dynamic_personas_map: * persona *
        persona_ids: * persona_ids *
        event_context: *
        player_name: *
    """
    if dynamic_personas_map is None:
        dynamic_personas_map = {}

    # * persona_ids*
    if persona_ids is None:
        persona_ids = ["mikko", "aino"]

    # * persona_ids *
    speaker_order = _decide_speaker_order(persona_ids, messages, user_content)

    # *
    if not speaker_order:
        return ""

    # * persona_ids*
    valid_persona_ids = [pid for pid in persona_ids if pid]
    if valid_persona_ids:
        def _get_display_name(pid):
            if pid in dynamic_personas_map:
                return dynamic_personas_map[pid].name
            return pid.capitalize()
        display_names = ", ".join([_get_display_name(pid) for pid in valid_persona_ids])
        print(f"[Backend] *: {display_names}")
        print(f"[Backend] *: {speaker_order}")

    replies = []
    history_text = _format_conversation_history(messages)

    # *"*"*
    all_participants = [pid for pid in persona_ids if pid]

    for persona_id in speaker_order:
        # *
        if persona_id in dynamic_personas_map:
            persona_name = dynamic_personas_map[persona_id].name
        else:
            persona_name = personas.PERSONAS[persona_id]["name"]

        # *
        other_name = ""
        if replies:
            # * replies *
            last_reply = replies[-1]
            for pid in all_participants:
                if pid in dynamic_personas_map:
                    pname = dynamic_personas_map[pid].name
                else:
                    pname = personas.PERSONAS[pid]["name"]
                if pname in last_reply:
                    other_name = pname
                    break

        # *
        prompt_parts = []

        # *
        if event_context and (event_context.get("title") or event_context.get("description")):
            event_text = "*\n"
            if event_context.get("title"):
                event_text += f"*{event_context['title']}\n"
            if event_context.get("description"):
                event_text += f"*{event_context['description']}\n"
            if event_context.get("topics"):
                event_text += f"*{', '.join(event_context['topics'])}\n"
            event_text += "*\n"
            prompt_parts.append(event_text)

        # *
        if history_text:
            prompt_parts.append(f"*\n{history_text}")

        # *
        if other_name:
            prompt_parts.append(f"*{other_name} *{replies[-1]}*")

        # *
        if player_name and player_name.strip():
            prompt_parts.append(f"{player_name}*{user_content}")
        else:
            prompt_parts.append(f"*{user_content}")
        prompt_parts.append("*1-2*")

        prompt = "\n\n".join(prompt_parts)

        # * persona*
        dynamic_persona = dynamic_personas_map.get(persona_id)
        reply = await _call_agent(conversation_id, persona_id, prompt, messages, dynamic_persona)
        if reply:
            # *
            replies.append(f"{persona_name}: {reply}")

    if replies:
        return "\n\n".join(replies)
    else:
        # *
        def _get_participant_name(pid):
            if pid in dynamic_personas_map:
                return dynamic_personas_map[pid].name
            return pid.capitalize()
        participants = [_get_participant_name(pid) for pid in all_participants]
        names_str = "*".join(participants)
        return f"*{names_str} *"


async def _call_observer(conversation_id: str, messages: List[dict]) -> str:
    """* Observer *"""
    runner = personas.RUNNERS["observer"]
    app_name = "persona_observer"
    session_id = _session_id("observer", conversation_id)
    persona_name = personas.PERSONAS["observer"]["name"]

    await _get_or_create_session(runner, app_name, session_id)

    # *
    history_text = _format_conversation_history(messages)
    user_msg = f"*\n\n{history_text}"

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
    persona_ids: List[str],
    conversation_id: str,
    dynamic_personas_map: Optional[Dict[str, DynamicPersona]] = None,
    event_context: Optional[dict] = None,
    player_name: Optional[str] = None
) -> List[dict]:
    """生成群聊初始消息（基于 dynamic persona 和 event）

    Args:
        persona_ids: 参与 ID 列表
        conversation_id: 会话 ID
        dynamic_personas_map: 动态 persona 映射 (从 Godot 传递)
        event_context: 事件上下文 (title, description, topics)
        player_name: 玩家名称（用于打招呼）
    """
    out: List[dict] = []

    if dynamic_personas_map is None:
        dynamic_personas_map = {}

    # 检查是否有事件上下文
    has_event = event_context is not None and (
        event_context.get("title") or
        event_context.get("description") or
        event_context.get("topics")
    )

    # 构建事件描述（用于开场白）
    event_description = ""
    if has_event:
        event_parts = []
        if event_context.get("title"):
            event_parts.append(f"事件主题：{event_context['title']}")
        if event_context.get("description"):
            event_parts.append(f"事件描述：{event_context['description']}")
        if event_context.get("topics"):
            topics_str = '、'.join(event_context['topics'][:3])  # 最多3个话题
            event_parts.append(f"讨论话题：{topics_str}")
        event_description = "\n".join(event_parts)
        print(f"[Backend] [EVENT] 事件信息:\n{event_description}")

    # 获取参与者名称（优先使用 dynamic persona）
    participant_names = {}
    for pid in persona_ids:
        if pid in dynamic_personas_map:
            participant_names[pid] = dynamic_personas_map[pid].name
        elif pid in personas.PERSONAS:
            participant_names[pid] = personas.PERSONAS[pid]["name"]
        else:
            participant_names[pid] = pid

    # 按顺序让每个 persona 发言
    for i, persona_id in enumerate(persona_ids):
        # 获取 persona 名称
        persona_name = participant_names.get(persona_id, persona_id)

        # 获取 dynamic persona（如果有）
        dynamic_persona = dynamic_personas_map.get(persona_id)

        # 构建开场提示
        prompt_parts = []

        # 首先让 agent 向 player 打招呼
        if player_name:
            prompt_parts.append(f"请先向 {player_name} 打个招呼。")
        
        # 添加事件描述（如果有）
        if has_event and event_description:
            prompt_parts.append("")
            prompt_parts.append(event_description)
            prompt_parts.append("")
            prompt_parts.append(f"现在你们正在讨论这个事件。请用1-2句话发起或参与讨论。")
        else:
            prompt_parts.append("")
            prompt_parts.append(f"请用1-2句话发起讨论。")

        # 添加之前的对话历史（如果有）
        if out:
            prompt_parts.append("")
            prompt_parts.append("之前的对话：")
            for prev_msg in out:
                if prev_msg.get("role") == "model":
                    prev_name = prev_msg.get("name", "")
                    prev_content = prev_msg.get("content", "")
                    if prev_name and prev_content:
                        prompt_parts.append(f"{prev_name}: {prev_content}")

        prompt_parts.append("")
        prompt_parts.append("要求：")
        prompt_parts.append("- 多数时候对 Player 说话，少数时候和其他 agent 交谈")
        prompt_parts.append("- 用第一人称，自然对话")
        prompt_parts.append("- 不要说思考过程")
        prompt_parts.append("- 根据你的性格、喜好和当前状态说话")

        # 如果有 dynamic persona，添加其 dislikes 提示
        if dynamic_persona and dynamic_persona.dislikes:
            prompt_parts.append(f"- 你不喜欢：{', '.join(dynamic_persona.dislikes)}")

        prompt = "\n".join(prompt_parts)

        # 调用 agent
        reply = await _call_agent(conversation_id, persona_id, prompt, out, dynamic_persona)

        if reply:
            out.append({"role": "model", "name": persona_name, "content": reply})
            print(f"[Backend] 开场白 - {persona_name}: {reply[:50]}...")

    return out


# ---------- RESTful: 创建会话 ----------


@app.post("/conversations", response_model=ConversationItem)
async def create_conversation(req: CreateConversationReq):
    """*

    * persona* dynamic_personas *

    * Analyser *
    """
    persona_ids = [p.strip().lower() for p in req.persona_ids if p.strip()]
    if not persona_ids:
        persona_ids = DEFAULT_PERSONAS.copy()  # *

    # * persona ID
    seen = set()
    duplicates = []
    for pid in persona_ids:
        if pid in seen:
            duplicates.append(pid)
        seen.add(pid)
    if duplicates:
        # * ID *
        from collections import Counter
        counts = Counter(persona_ids)
        dup_details = ", ".join(f"{pid} * {counts[pid]} *" for pid in set(duplicates))
        raise HTTPException(
            400,
            detail=f"*: {dup_details}",
        )

    # * persona *
    dynamic_personas_map: Dict[str, DynamicPersona] = {}
    for dp in req.dynamic_personas:
        dynamic_personas_map[dp.id] = dp

    # * persona IDs* persona *
    invalid = []
    for p in persona_ids:
        if p not in personas.PERSONAS and p not in dynamic_personas_map:
            invalid.append(p)

    if invalid:
        available = list(personas.PERSONAS.keys()) + list(dynamic_personas_map.keys())
        raise HTTPException(
            400,
            detail=f"*: {', '.join(invalid)}*: {', '.join(available)}*",
        )

    conv_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    # * dynamic_personas *
    # * dynamic_personas *
    event_context = None
    if req.dynamic_personas and len(req.dynamic_personas) > 0:
        # * dynamic persona*
        first_dp = req.dynamic_personas[0]
        if hasattr(first_dp, 'event_title') or hasattr(first_dp, 'event_description'):
            event_context = {
                "title": getattr(first_dp, 'event_title', ''),
                "description": getattr(first_dp, 'event_description', ''),
                "topics": getattr(first_dp, 'event_topics', []),
                "required_topics": getattr(first_dp, 'required_topics', []),
            }
            print(f"[Event] *: {event_context}")

    CONVERSATIONS[conv_id] = {
        "persona_ids": persona_ids,
        "messages": [],
        "created_at": now,
        "dynamic_personas": req.dynamic_personas,  # * persona *
        "event_context": event_context,  # *
    }

    # *
    is_finnish_pair = len(persona_ids) == 2 and set(persona_ids) == {"mikko", "aino"}
    if len(persona_ids) >= 2 or is_finnish_pair:
        try:
            # [EVENT] * event_context *
            initial = await _generate_group_initial_messages(
                persona_ids,
                conv_id,
                dynamic_personas_map,
                event_context,  # *
                req.player_name  # 传递玩家名字
            )
            CONVERSATIONS[conv_id]["messages"] = initial
        except Exception as e:
            print(f"[WARNING] *: {e}")
            import traceback
            traceback.print_exc()
            # *
            if event_context and event_context.get("title"):
                default_opening = f"Moi! {event_context['title']}*"
            else:
                default_opening = "Moi! *"
            CONVERSATIONS[conv_id]["messages"] = [
                {"role": "model", "name": "Mikko", "content": default_opening},
                {"role": "model", "name": "Aino", "content": "Selv[OK]! *"}
            ]
    msgs = CONVERSATIONS[conv_id]["messages"]
    return ConversationItem(
        id=conv_id,
        persona_ids=persona_ids,
        messages=[MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in msgs],
        created_at=now,
    )


@app.get("/conversations", response_model=List[ConversationSummary])
def list_conversations():
    """* default_ *"""
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
    """*"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="*")
    msgs = c["messages"]
    return ConversationItem(
        id=conversation_id,
        persona_ids=c["persona_ids"],
        messages=[MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in msgs],
        created_at=c["created_at"],
    )


@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, limit: Optional[int] = None, offset: int = 0):
    """* limit/offset *"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="*")
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
    """* Observer *"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="*")

    # * Observer *
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
    """*"""
    c = CONVERSATIONS.get(conversation_id)
    if not c:
        raise HTTPException(404, detail="*")
    # [FIX] * req.persona_id * content
    persona_id = req.persona_id if req.persona_id else None
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(400, detail="*")
    prev_len = len(c["messages"])
    try:
        combined = await _run_chat_round(conversation_id, c["persona_ids"], content, req.player_name)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    new_msgs = c["messages"][prev_len:]
    return {
        "messages": [MessageItem(role=m["role"], name=m.get("name"), content=m["content"]) for m in new_msgs],
        "reply": combined,
    }


# ============================================================================
# Analyser - 对话质量评估
# ============================================================================

async def _call_analyser(
    conversation_id: str,
    messages: List[dict],
    event_context: Optional[dict] = None,
    round_number: int = 0
) -> dict:
    """调用 Analyser 评估对话质量"""
    runner = personas.RUNNERS.get("analyser")
    if not runner:
        print("[Analyser] WARNING: analyser runner not found")
        return {"passed": False, "error": "Analyser not available"}

    app_name = "persona_analyser"
    session_id = _session_id("analyser", conversation_id)
    await _get_or_create_session(runner, app_name, session_id)

    persona_name = personas.PERSONAS.get("analyser", {}).get("name", "Analyser")

    # 构建评估提示
    prompt_parts = ["请评估以下对话质量：\n"]
    prompt_parts.append(f"对话历史：\n{_format_conversation_history(messages)}\n")

    # 添加事件上下文
    if event_context:
        if event_context.get("title"):
            prompt_parts.append(f"事件主题：{event_context['title']}\n")
        if event_context.get("description"):
            prompt_parts.append(f"事件描述：{event_context['description']}\n")
        if event_context.get("topics"):
            topics_str = ', '.join(event_context['topics'])
            prompt_parts.append(f"讨论话题：{topics_str}\n")

    # 添加评估标准
    prompt_parts.append("\n评估标准：")
    prompt_parts.append("✅ 对话充分性（必须满足）：")
    prompt_parts.append("- 是否讨论了事件的核心主题")
    prompt_parts.append("- Player 和 Agent 是否有有效互动")
    prompt_parts.append("- 对话轮次 ≥ 3")
    prompt_parts.append("\n✅ 主题相关性（必须满足）：")
    prompt_parts.append("- 对话内容与事件主题相关")
    prompt_parts.append("- 没有长时间偏离到无关话题")
    prompt_parts.append("\n✅ 个人喜好保持（必须满足）：")
    prompt_parts.append("- Agents 表达了 dislikes")

    # 添加输出格式说明
    prompt_parts.append("\n请按以下 JSON 格式输出（不要添加 markdown 标记）：")
    prompt_parts.append('```json')
    prompt_parts.append('{"passed": true/false,')
    prompt_parts.append('"overall_score": 0-100,')
    prompt_parts.append('"criteria": {')
    prompt_parts.append('  "topic_relevance": {"passed": true/false, "score": 0-100, "reason": "评估理由"}')
    prompt_parts.append('  "discussion_depth": {"passed": true/false, "score": 0-100, "reason": "评估理由"}')
    prompt_parts.append('  "dislikes_maintained": {"passed": true/false, "score": 0-100, "reason": "评估理由"}')
    prompt_parts.append('},')
    prompt_parts.append('"issues": ["发现的问题列表"]')
    prompt_parts.append('"suggestions": ["改进建议列表"]')
    prompt_parts.append('"needs_intervention": true/false')
    prompt_parts.append('}')

    # 如果是第5轮，添加 emoji 建议功能
    if round_number >= 5:
        prompt_parts.append("\n第5轮特殊任务 - Emoji 建议：")
        prompt_parts.append("当对话进行到第5轮时，额外提供 emoji_suggestion 字段：")
        prompt_parts.append('```json')
        prompt_parts.append('{"emoji_suggestion": {')
        prompt_parts.append('  "mood": "当前对话氛围，如: happy, excited, confused, tired, amused"')
        prompt_parts.append('  "emojis": ["😊", "🎉"]')
        prompt_parts.append('  "target_agents": ["mikko", "aino"]')
        prompt_parts.append('  "reason": "为什么建议这些emoji"')
        prompt_parts.append('}')
        prompt_parts.append('```')

    prompt_parts.append(f"\n对话轮次：{round_number}\n")

    user_msg = types.Content(role="user", parts=[types.Part(text="\n".join(prompt_parts))])
    events = []
    try:
        async for evt in runner.run_async(
            user_id=USER_ID, session_id=session_id, new_message=user_msg
        ):
            events.append(evt)

            # Log tool call events
            if hasattr(evt, 'content') and evt.content:
                if hasattr(evt.content, 'parts'):
                    for part in evt.content.parts or []:
                        if hasattr(part, 'function_call') and part.function_call is not None and hasattr(part.function_call, 'name'):
                            print(f"[Analyser][TOOL CALL] {persona_name} -> {part.function_call.name}({part.function_call.args})")
                        elif hasattr(part, 'function_response') and part.function_response is not None:
                            print(f"[Analyser][TOOL RESULT] {persona_name} <- {part.function_response.response}")

    except Exception as e:
        print(f"[Analyser] ERROR: {e}")
        import traceback
        traceback.print_exc()

    ai_reply = _get_reply_from_events(events)
    if ai_reply:
        try:
            # 尝试解析 JSON（移除可能的 markdown 标记）
            clean_reply = ai_reply.strip()
            if clean_reply.startswith("```json"):
                clean_reply = clean_reply[7:]
            if clean_reply.startswith("```"):
                clean_reply = clean_reply[3:]
            # 移除后3个字符（包括可能的结束标记）
            if clean_reply.endswith("```"):
                clean_reply = clean_reply[:-3]

            import json
            evaluation = json.loads(clean_reply)
            print(f"[Analyser] 评估结果: passed={evaluation.get('passed')}, score={evaluation.get('overall_score', 'N/A')}")
        except json.JSONDecodeError as e:
            print(f"[Analyser] JSON 解析失败: {e}")
            # 返回默认错误响应
            evaluation = {
                "passed": False,
                "error": f"JSON decode error: {str(e)}",
                "raw_reply": ai_reply[:200] if ai_reply else "N/A"
            }

    messages.append({"role": "model", "name": persona_name, "content": ai_reply})
    return evaluation


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
