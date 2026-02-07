# Main.py 逻辑架构说明

**版本**: v2.1 (1016 行)
**更新日期**: 2025-02-08

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 应用                           │
│                     (Main.py 入口)                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      数据模型层                              │
│  - PersonaItem                                              │
│  - DynamicPersona (新增)                                    │
│  - CreateConversationReq (扩展)                             │
│  - MessageItem                                              │
│  - ConversationItem                                         │
│  - ConversationSummary                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     全局状态存储                             │
│  - CONVERSATIONS: 会话数据                                   │
│  - CONVERSATION_STATES: 对话状态机                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      API 路由层                              │
│  GET  /personas                                             │
│  POST /conversations                                        │
│  GET  /conversations/{id}                                   │
│  GET  /conversations/{id}/messages                          │
│  POST /conversations/{id}/messages                          │
│  GET  /conversations/{id}/summary                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     业务逻辑层                               │
│  - 状态机 (_run_chat_round)                                  │
│  - Agent 调用 (_call_agent, _expert_respond, _call_observer) │
│  - 群聊编排 (_finnish_students_respond)                       │
│  - 开场生成 (_generate_group_initial_messages)                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     工具函数层                               │
│  - 对话格式化 (_format_conversation_history)                  │
│  - 动态指令生成 (_generate_dynamic_persona_instruction)       │
│  - 思考标签清理 (_strip_thinking, _get_reply_from_events)    │
│  - 发言顺序决策 (_decide_speaker_order)                       │
│  - 关键词检测 (_detect_focus_flags)                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   外部依赖层                                 │
│  - personas.py (Persona 配置 + ADK Runner)                   │
│  - Google ADK (Agent 开发工具包)                             │
│  - LiteLlm (统一模型接口)                                    │
│  - Ollama / Azure OpenAI (模型服务)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心数据结构

### 2.1 数据模型（Pydantic BaseModel）

```python
# 请求/响应模型
class PersonaItem(BaseModel):
    id: str
    name: str

class DynamicPersona(BaseModel):           # 新增 v2.1
    id: str
    name: str
    gender: str = "Male"
    personality: str = ""
    personality_type: str = "Extrovert"
    interests: str = ""
    speaking_style: str = ""
    likes: list[str] = []
    dislikes: list[str] = []
    current_state: str = ""
    location_hint: str = ""

class CreateConversationReq(BaseModel):
    persona_ids: list[str]
    dynamic_personas: list[DynamicPersona] = []  # 新增 v2.1

class MessageItem(BaseModel):
    role: str
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
```

### 2.2 全局状态存储

```python
# 会话存储：id -> { persona_ids, messages, created_at, dynamic_personas }
CONVERSATIONS: dict[str, dict] = {}

# 会话状态管理：id -> {
#     "phase": "small_talk" | "religion_deep" | "allergy_deep" | "wrap_up" | "finished",
#     "religion_discussed": bool,
#     "allergy_discussed": bool,
#     "sub_agent_turns": int,
# }
CONVERSATION_STATES: dict[str, dict] = {}

# 配置常量
USER_ID = "godot"
DEFAULT_PERSONAS = ["mikko", "aino"]
MAX_REPLY_LENGTH = 2000
```

---

## 三、API 路由层

### 3.1 路由列表

| 方法 | 端点 | 处理函数 | 功能 |
|------|------|----------|------|
| GET | `/` | `root()` | 根路径，返回 API 信息 |
| GET | `/favicon.ico` | `favicon()` | 返回 204，避免 404 |
| GET | `/personas` | `list_personas()` | 获取可用 persona 列表 |
| POST | `/conversations` | `create_conversation()` | 创建会话（支持动态 persona） |
| GET | `/conversations` | `list_conversations()` | 获取会话列表 |
| GET | `/conversations/{id}` | `get_conversation()` | 获取会话详情 |
| GET | `/conversations/{id}/messages` | `get_conversation_messages()` | 获取消息列表（分页） |
| POST | `/conversations/{id}/messages` | `post_conversation_message()` | 发送消息 |
| GET | `/conversations/{id}/summary` | `get_conversation_summary()` | 获取 Observer 总结 |

### 3.2 路由详解

#### POST /conversations (创建会话)

```python
async def create_conversation(req: CreateConversationReq):
    """
    1. 解析 persona_ids
    2. 检测重复 ID
    3. 验证 persona（预定义或动态）
    4. 创建会话对象
    5. 生成开场对话（如果是多人或芬兰学生组合）
    6. 返回会话详情
    """
```

**流程图**：
```
请求 → 验证参数 → 创建会话 → 保存动态 persona → 生成开场 → 返回结果
```

#### POST /conversations/{id}/messages (发送消息)

```python
async def post_conversation_message(conversation_id: str, req: PostMessageReq):
    """
    1. 获取会话对象
    2. 追加用户消息
    3. 调用 _run_chat_round 处理
    4. 返回新增消息和合并回复
    """
```

**流程图**：
```
请求 → 验证会话 → 追加消息 → 状态机处理 → 返回回复
```

---

## 四、业务逻辑层

### 4.1 状态机架构（芬兰学生对话）

```
┌──────────────┐
│  small_talk  │ ← 初始状态
└──────────────┘
      ↓ 检测关键词
┌──────────────┐
│religion_deep │ ← 用户提到宗教相关
│allergy_deep  │ ← 用户提到过敏相关
└──────────────┘
      ↓ 3-4 轮讨论
┌──────────────┐
│  small_talk  │ ← 返回闲聊
└──────────────┘
      ↓ 两个话题都讨论过
┌──────────────┐
│   wrap_up    │ ← 收尾阶段
└──────────────┘
      ↓ 用户确认
┌──────────────┐
│  finished    │ ← 调用 Observer
└──────────────┘
```

### 4.2 核心函数调用链

#### 创建会话流程

```
create_conversation()
    ├─ 验证 persona_ids
    ├─ 验证 dynamic_personas
    ├─ 创建 CONVERSATIONS[conv_id]
    └─ _generate_group_initial_messages()
            ├─ _call_agent(mikko) → Mikko 开场
            └─ _call_agent(aino) → Aino 回应
```

#### 发送消息流程

```
post_conversation_message()
    └─ _run_chat_round()
            ├─ 获取/初始化状态
            ├─ 追加用户消息
            ├─ 状态机转换
            └─ 根据状态调用 Agent：
                ├─ small_talk → _finnish_students_respond()
                │       └─ _call_agent() × 2 (轮流发言)
                ├─ religion_deep → _expert_respond(religion_expert)
                │       ├─ _call_agent(religion_expert)
                │       └─ _call_agent(aino) [补充]
                ├─ allergy_deep → _expert_respond(allergy_expert)
                │       ├─ _call_agent(allergy_expert)
                │       └─ _call_agent(mikko) [补充]
                ├─ wrap_up → _finnish_students_respond()
                │       └─ _call_observer() [如果进入 finished]
                └─ finished → _call_observer()
```

#### Agent 调用流程

```
_call_agent(persona_id, prompt, messages, dynamic_persona?)
    ├─ 获取 personas.RUNNERS[persona_id]
    ├─ 生成/获取 session
    ├─ 如果有 dynamic_persona：
    │   └─ _generate_dynamic_persona_instruction()
    ├─ 构建 new_message
    ├─ runner.run_async() → 生成 events
    ├─ _get_reply_from_events(events)
    │       └─ _strip_thinking(reply)
    └─ 返回 ai_reply
```

---

## 五、工具函数层

### 5.1 对话处理函数

```python
# 格式化对话历史
def _format_conversation_history(messages: list[dict]) -> str
    # 将消息列表转换为文本格式
    # "玩家: xxx" 或 "Mikko: xxx"

# 清理思考标签
def _strip_thinking(text: str) -> str
    # 移除 <think> 标签
    # 提取真实对话内容
    # 限制长度

# 从 events 提取回复
def _get_reply_from_events(events)
    # 过滤 role="model" 的内容
    # 去重
    # 调用 _strip_thinking
```

### 5.2 动态 Persona 函数

```python
# 生成动态 persona 指令
def _generate_dynamic_persona_instruction(dynamic_persona: DynamicPersona) -> str
    # 映射 gender → 中文
    # 映射 personality_type → 中文
    # 组合所有字段生成完整指令
    # 返回格式化的 AI 提示词
```

### 5.3 决策函数

```python
# 决定发言顺序
def _decide_speaker_order(messages: list[dict], user_content: str) -> list[str]
    # 规则1: 用户直接提问 → 该角色先答
    # 规则2: 上一个发言者 → 交替
    # 规则3: 随机性 → 30% 概率只有一人发言
    # 返回 [persona_id1, persona_id2]

# 检测关键词
def _detect_focus_flags(user_content: str) -> tuple[bool, bool]
    # 检测宗教关键词
    # 检测过敏关键词
    # 返回 (has_religion, has_allergy)
```

---

## 六、数据流

### 6.1 创建会话数据流

```
Client                          Main.py                     personas.py
  │                               │                              │
  ├─ POST /conversations ────────>│                              │
  │  {persona_ids,                │                              │
  │   dynamic_personas}           │                              │
  │                               ├─ 验证 persona_ids ──────────>│
  │                               │  (预定义列表)                │
  │                               ├─ 创建会话对象               │
  │                               │  CONVERSATIONS[id]           │
  │                               ├─ 调用 _generate_group...    │
  │                               │  ├─ _call_agent(mikko) ────>│
  │                               │  │  └─ RUNNERS[mikko]       │
  │                               │  │     └─ ADK Agent        │
  │                               │  │        └─ LiteLlm       │
  │                               │  │           └─ Ollama/Azure│
  │                               │  │                          │
  │                               │  └─ _call_agent(aino) ────>│
  │                               │                             │
  │<─ 返回会话详情 ─────────────────┤                             │
  │  {id, persona_ids,             │                             │
  │   messages}                    │                             │
```

### 6.2 发送消息数据流

```
Client                          Main.py                     personas.py
  │                               │                              │
  ├─ POST /conversations/{id}/    │                              │
  │    messages ─────────────────>│                              │
  │  {content}                    │                              │
  │                               ├─ _run_chat_round()          │
  │                               │  ├─ 获取状态                │
  │                               │  ├─ 状态机转换              │
  │                               │  └─ 调用 Agent ───────────>│
  │                               │     └─ RUNNERS[persona]     │
  │                               │        └─ ADK              │
  │                               │           └─ LiteLlm       │
  │                               │              └─ Ollama/Azure│
  │                               │                             │
  │<─ 返回回复 ───────────────────┤                             │
  │  {messages, reply}            │                             │
```

---

## 七、关键特性实现

### 7.1 动态 Persona 支持

**存储结构**：
```python
CONVERSATIONS[conv_id] = {
    "persona_ids": ["mikko", "sarah"],
    "messages": [...],
    "created_at": "2025-02-08T...",
    "dynamic_personas": [
        DynamicPersona(id="sarah", name="Sarah", ...)
    ]
}
```

**使用流程**：
1. 创建会话时接收 `dynamic_personas`
2. 创建映射表 `dynamic_personas_map`
3. 调用 Agent 时传递 `dynamic_persona`
4. 生成动态指令并注入 prompt

### 7.2 Gender 参数影响

**代码位置**：`_generate_dynamic_persona_instruction()`

```python
# Gender 映射
gender_map = {
    "Male": "男性",
    "Female": "女性",
    "Non-binary": "非二元性别",
    "Other": "其他性别"
}

# 添加性别提示
if dynamic_persona.gender == "Male":
    instruction += "你是男性角色，请用男性的口吻说话。\n"
elif dynamic_persona.gender == "Female":
    instruction += "你是女性角色，请用女性的口吻说话。\n"
```

### 7.3 重复检测

**代码位置**：`create_conversation()`

```python
seen = set()
duplicates = []
for pid in persona_ids:
    if pid in seen:
        duplicates.append(pid)
    seen.add(pid)

if duplicates:
    raise HTTPException(400, detail=f"检测到重复的聊天对象: ...")
```

### 7.4 思考标签清理

**代码位置**：`_strip_thinking()`

```python
# 移除 <think>...</think> 标签
text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)

# 查找对话开始位置
# 提取真实对话内容
# 限制长度到 MAX_REPLY_LENGTH
```

---

## 八、错误处理

### 8.1 验证错误

| 错误类型 | HTTP 状态码 | 触发条件 |
|---------|-------------|---------|
| 重复 persona ID | 400 | persona_ids 中有重复 |
| 未知 persona | 400 | ID 不在预定义列表且不在 dynamic_personas 中 |
| 会话不存在 | 404 | conversation_id 无效 |
| 消息内容为空 | 400 | content 为空字符串 |
| Azure 配置错误 | 500 | USE_AZURE=true 但缺少环境变量 |

### 8.2 运行时错误

```python
try:
    # 调用 ADK
    reply = await _call_agent(...)
except ValueError as e:
    raise HTTPException(404, detail=str(e))
except Exception as e:
    # 记录日志
    print(f"[WARNING] 生成开场对话失败: {e}")
    # 使用默认值
```

---

## 九、性能优化

### 9.1 会话缓存

```python
CONVERSATIONS: dict[str, dict] = {}
# 内存存储，避免数据库查询
# 会话结束后自动清理（可选）
```

### 9.2 Session 复用

```python
def _session_id(persona_id: str, conversation_id: str | None = None):
    if conversation_id:
        return conversation_id  # 同一会话复用 session
    return f"default_{persona_id}"  # 默认 session
```

### 9.3 回复长度限制

```python
MAX_REPLY_LENGTH = 2000
# 避免超长回复导致 Godot 显示问题
```

---

## 十、扩展性设计

### 10.1 模型切换

```python
# personas.py 中配置
USE_AZURE = os.getenv("USE_AZURE", "false").lower() == "true"

# 无需修改 Main.py
```

### 10.2 Persona 扩展

**方式1**：修改 personas.py（预定义）
```python
PERSONAS["new_persona"] = {...}
RUNNERS["new_persona"] = Agent(...)
```

**方式2**：使用 DynamicPersona（动态）
```json
POST /conversations
{
  "persona_ids": ["new_id"],
  "dynamic_personas": [{"id": "new_id", "name": "New", ...}]
}
```

### 10.3 状态机扩展

在 `_run_chat_round()` 中添加新的 phase：
```python
elif phase == "new_phase":
    # 新的处理逻辑
    return await _new_phase_handler(...)
```

---

## 十一、测试建议

### 11.1 单元测试

```python
# 测试状态机转换
def test_state_machine_transitions():
    # small_talk → religion_deep
    # religion_deep → small_talk
    # ...

# 测试动态 persona
def test_dynamic_persona_instruction():
    dp = DynamicPersona(...)
    instruction = _generate_dynamic_persona_instruction(dp)
    assert "男性" in instruction
```

### 11.2 集成测试

```python
# 测试完整对话流程
async def test_conversation_flow():
    # 1. 创建会话
    # 2. 发送消息
    # 3. 验证回复
    # 4. 验证状态转换
```

### 11.3 性能测试

```python
# 测试并发会话
async def test_concurrent_conversations():
    # 创建 10 个会话
    # 并发发送消息
    # 验证响应时间
```

---

## 十二、版本演进

### v2.1 (2025-02-08)
- ✅ 添加 DynamicPersona 类
- ✅ 添加 gender 参数支持
- ✅ 修改所有核心函数支持动态 persona
- ✅ 扩展会话存储结构

### v2.0
- ✅ 状态机架构（Finnish discussion group）
- ✅ 重复 persona ID 检测
- ✅ 群聊开场对话生成逻辑修复

### v1.0
- ✅ 基础 REST API
- ✅ 多 persona 支持
- ✅ 对话历史管理

---

## 总结

Main.py 采用分层架构：
1. **数据模型层**：Pydantic BaseModel
2. **API 路由层**：FastAPI 路由处理
3. **业务逻辑层**：状态机、Agent 调用
4. **工具函数层**：辅助功能函数
5. **外部依赖层**：personas.py、ADK、LiteLlm

**核心特性**：
- 动态 persona 支持
- 状态机对话管理
- 混合模式（预定义 + 动态）
- 完善的错误处理
- 高性能缓存设计

**扩展性**：
- 支持模型切换（Ollama/Azure）
- 支持 persona 扩展（预定义/动态）
- 支持状态机扩展
