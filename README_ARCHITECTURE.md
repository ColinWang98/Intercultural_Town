# 项目逻辑架构

本文档总结当前 Backend + Godot 2D 项目的整体逻辑架构、数据流与核心模块职责。

---

## 一、整体分层

```
┌─────────────────────────────────────────────────────────────────┐
│  Godot 前端 (chat_interface_group.gd + game_state_2d.gd)         │
│  REST 调用：POST /conversations → POST /conversations/{id}/messages │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Main.py (FastAPI)                                               │
│  - 会话存储 CONVERSATIONS                                        │
│  - 状态机 CONVERSATION_STATES（phase 管理）                      │
│  - REST 路由与请求校验                                           │
│  - 对话编排：_run_chat_round（状态机驱动）                        │
│  - 专家附身：_expert_respond                                     │
│  - 开场生成：_generate_group_initial_messages                     │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  personas.py                                                     │
│  - PERSONAS 配置（模型、instruction）                            │
│  - 主角色：mikko、aino（芬兰学生）                               │
│  - 子代理：religion_expert、allergy_expert（专家）               │
│  - Observer：总结对话 + 鼓励性反馈                               │
│  - 每个 persona 一个 Agent + InMemoryRunner                      │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Google ADK + LiteLlm + Ollama                                   │
│  - 每个 Runner 独立 session（session_id = conversation_id）      │
│  - run_async() 产生 events，从中抽取 model 文本                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、核心数据流

### 2.1 会话与消息存储

- **CONVERSATIONS**：`{conversation_id: {persona_ids, messages, created_at}}`
- **CONVERSATION_STATES**：`{conversation_id: {phase, religion_discussed, allergy_discussed, sub_agent_turns}}`
- **messages**：`[{role, name, content}, ...]`，`role` 为 `"user"` 或 `"model"`
- 每个会话有唯一 `conversation_id`（uuid），前端用 `GameState.current_conversation_id` 缓存

### 2.2 创建会话（POST /conversations）

1. 校验 `persona_ids` 是否在 `personas.PERSONAS` 中
2. 生成 `conv_id`，初始化 `{persona_ids, messages: [], created_at}`
3. 若为芬兰学生组合（mikko + aino）或多人群聊：调用 `_generate_group_initial_messages` 生成开场
4. 芬兰学生开场：Mikko 先开口，Aino 回应；其他组合：每人发一条群聊开场
5. 返回 `ConversationItem`（含 `id`、`persona_ids`、`messages`、`created_at`）

### 2.3 发送消息（POST /conversations/{id}/messages）

1. 校验会话存在、`content` 非空
2. 调用 `_run_chat_round(conversation_id, persona_ids, user_content)`（状态机驱动）
3. 返回本轮新增的 `messages` 和合并后的 `reply`

---

## 三、状态机架构（_run_chat_round）

### 3.1 状态阶段

| phase | 说明 | 调用 Agent |
|-------|------|------------|
| `small_talk` | 闲聊阶段，检测关键词 | mikko、aino（轮流） |
| `religion_deep` | 宗教专家主导（附身 Mikko） | religion_expert（显示为 Mikko）+ aino 可选补充 |
| `allergy_deep` | 过敏专家主导（附身 Aino） | allergy_expert（显示为 Aino）+ mikko 可选补充 |
| `wrap_up` | 收尾阶段 | mikko、aino（轮流） |
| `finished` | 完成，调用 Observer | observer |

### 3.2 状态转换逻辑

1. **small_talk → religion_deep**：
   - 玩家消息包含宗教关键词（宗教、清真、穆斯林、halal、kosher、素食等）
   - 且 `religion_discussed == False`
   - 转换后：`sub_agent_turns = 0`

2. **small_talk → allergy_deep**：
   - 玩家消息包含过敏关键词（过敏、花生、坚果、海鲜、乳糖、麸质等）
   - 且 `allergy_discussed == False`
   - 转换后：`sub_agent_turns = 0`

3. **religion_deep → small_talk / wrap_up**：
   - `sub_agent_turns >= 3`（3-4 轮后）
   - 设置 `religion_discussed = True`
   - 若 `allergy_discussed == True` → `wrap_up`，否则 → `small_talk`

4. **allergy_deep → small_talk / wrap_up**：
   - `sub_agent_turns >= 3`（3-4 轮后）
   - 设置 `allergy_discussed = True`
   - 若 `religion_discussed == True` → `wrap_up`，否则 → `small_talk`

5. **small_talk → wrap_up**：
   - `religion_discussed == True` 且 `allergy_discussed == True`

6. **wrap_up → finished**：
   - 玩家消息包含确认词（是、好了、可以、没问题、考虑清楚了、没了、没有）

### 3.3 各阶段响应逻辑

- **small_talk**：调用 `_finnish_students_respond`（mikko、aino 轮流，动态决定顺序）
- **religion_deep**：调用 `_expert_respond(religion_expert, "Mikko")`，Aino 可选补充
- **allergy_deep**：调用 `_expert_respond(allergy_expert, "Aino")`，Mikko 可选补充
- **wrap_up**：调用 `_finnish_students_respond`，若已 `finished` 则追加 `_call_observer`
- **finished**：只返回 `_call_observer` 的总结

---

## 四、Persona 与 Runner 构建（personas.py）

### 4.1 Persona 列表

| id | 显示名 | 模型 | 用途 |
|----|--------|------|------|
| mikko | Mikko | ollama_chat/qwen3:4b-instruct | 芬兰学生（外向热情），主角色 |
| aino | Aino | ollama_chat/qwen3:4b-instruct-2507-fp16 | 芬兰学生（细心有条理），主角色 |
| religion_expert | 宗教禁忌专家 | ollama_chat/qwen3:4b-instruct | 子代理，附身 Mikko 时调用 |
| allergy_expert | 食物过敏专家 | ollama_chat/qwen3:4b-instruct-2507-fp16 | 子代理，附身 Aino 时调用 |
| observer | 对话观察者 | ollama_chat/qwen3:8b | 总结对话 + 鼓励性反馈 |

### 4.2 Runner 构建流程

1. 为每个 persona 创建 Agent（无工具）
2. 用 `tools.register_agent_tool` 将每个 Agent 包装为 AgentTool（供未来使用）
3. 为每个 Agent 创建 `InMemoryRunner`，`app_name = f"persona_{pid}"`

### 4.3 Session 映射

- `session_id = conversation_id`（同一会话内所有 persona 共用同一 conversation_id 作为 ADK session）
- `user_id = "godot"`：所有请求统一用户标识

---

## 五、核心函数

| 函数 | 用途 |
|------|------|
| `_format_conversation_history` | 将 messages 转为 `"玩家: xxx\n角色: xxx"` 文本 |
| `_strip_thinking` | 移除思考前缀（"首先"、"我需要"、"用户希望"等） |
| `_get_reply_from_events` | 从 ADK events 抽取 model 文本，去重、拼接、截断 |
| `_session_id` | 返回 conversation_id 或 `default_{persona_id}` |
| `_get_or_create_session` | 获取或创建 ADK session |
| `_detect_focus_flags` | 检测玩家消息是否包含宗教/过敏关键词 |
| `_decide_speaker_order` | 动态决定 mikko/aino 发言顺序（交替或按玩家提问） |
| `_call_agent` | 通用 Agent 调用（给定 prompt，返回回复并写回 messages） |
| `_finnish_students_respond` | 芬兰学生轮流响应（使用 `_decide_speaker_order`） |
| `_expert_respond` | 专家附身模式（专家以角色身份回应，检查 `[DONE]` 标记） |
| `_call_observer` | 调用 Observer 生成总结（传入对话历史） |
| `_generate_group_initial_messages` | 群聊开场：芬兰学生特殊流程（Mikko → Aino），其他通用流程 |

---

## 六、REST API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /personas | 返回 persona 列表 |
| POST | /conversations | 创建会话，芬兰学生组合时自动生成开场 |
| GET | /conversations | 会话列表（摘要） |
| GET | /conversations/{id} | 单会话详情（含消息） |
| GET | /conversations/{id}/messages | 消息列表（支持 limit、offset） |
| GET | /conversations/{id}/summary | 获取 Observer 对话总结 |
| POST | /conversations/{id}/messages | 发送消息，返回本轮新增消息及合并 reply |

---

## 七、Godot 端要点

- **GameState**（Autoload）：`current_conversation_id`、`nearby_agents`、`last_ai_reply`、`last_player_message`
- **chat_interface_group.gd**：无会话时先 `POST /conversations`，有会话后 `POST /conversations/{id}/messages`
- **Dialogue Manager**：`npc_reply.dialogue`、`player_reply.dialogue` 通过 `{{ GameState.last_ai_reply }}`、`{{ GameState.last_player_message }}` 显示气泡

---

## 八、状态机流程示例

```
玩家："今晚聚餐准备得怎么样了？"
→ small_talk: Mikko 和 Aino 轮流回应

玩家："有没有清真食品？"
→ 检测到宗教关键词 → religion_deep
→ religion_expert（显示为 Mikko）主导，Aino 可选补充
→ 3 轮后 → religion_discussed = True → small_talk

玩家："有人对花生过敏吗？"
→ 检测到过敏关键词 → allergy_deep
→ allergy_expert（显示为 Aino）主导，Mikko 可选补充
→ 3 轮后 → allergy_discussed = True → wrap_up（因为 religion_discussed 已为 True）

玩家："好了，没问题了"
→ wrap_up → finished
→ Observer 生成总结 + 鼓励性反馈
```

---

## 九、关键设计决策

1. **状态机驱动**：根据玩家输入动态切换对话阶段，而非固定流程
2. **专家附身**：专家以角色身份（Mikko/Aino）回应，保持角色一致性
3. **动态发言顺序**：根据玩家提问或上次发言者决定 mikko/aino 顺序
4. **关键词检测**：只在玩家当前消息中检测，不扫描历史（避免误触发）
5. **子代理轮数控制**：专家讨论 3-4 轮后自动返回闲聊或收尾
6. **Observer 总结**：仅在 `finished` 阶段自动调用，也可通过 `GET /conversations/{id}/summary` 手动获取
