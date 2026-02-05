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
│  - REST 路由与请求校验                                           │
│  - 对话编排：_run_chat_round、_generate_group_initial_messages   │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  personas.py + tools.py                                          │
│  - PERSONAS 配置（模型、instruction）                            │
│  - 每个 persona 一个 Agent + InMemoryRunner                      │
│  - 法国学生互问：AgentTool（french_student_male ↔ female）       │
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
- **messages**：`[{role, name, content}, ...]`，`role` 为 `"user"` 或 `"model"`
- 每个会话有唯一 `conversation_id`（uuid），前端用 `GameState.current_conversation_id` 缓存

### 2.2 创建会话（POST /conversations）

1. 校验 `persona_ids` 是否在 `personas.PERSONAS` 中
2. 生成 `conv_id`，初始化 `{persona_ids, messages: [], created_at}`
3. 若 `persona_ids` 至少 2 个：调用 `_generate_group_initial_messages` 生成开场
4. 两位法国学生：男先发言，女再回应；其他组合：每人发一条群聊开场
5. 返回 `ConversationItem`（含 `id`、`persona_ids`、`messages`、`created_at`）

### 2.3 发送消息（POST /conversations/{id}/messages）

1. 校验会话存在、`content` 非空
2. 调用 `_run_chat_round(conversation_id, persona_ids, user_content)`
3. 返回本轮新增的 `messages` 和合并后的 `reply`

---

## 三、对话编排逻辑（_run_chat_round）

1. **追加用户消息**：`messages.append({role:"user", name:None, content})`
2. **格式化历史**：`_format_conversation_history(messages)` → `"玩家: xxx\n角色A: xxx\n..."`
3. **按 persona 依次调用**：
   - 每个 persona 对应一个 Runner，`session_id = conversation_id`（同一会话共享）
   - **单人**：直接发 `user_content`
   - **群聊**：发 `【群聊模式】... + 历史 + 你是 X，请参与对话。【协作规则】可用 ask_agent 工具询问其他角色`
4. **收集回复**：从 `runner.run_async()` 的 events 中取 model 文本，经 `_get_reply_from_events` 处理
5. **后处理**：`_strip_thinking` 去掉 `<think>` 等思考标签；单次回复截断至 `MAX_REPLY_LENGTH`（2000 字符）
6. **写回会话**：每条回复追加为 `{role:"model", name: persona_name, content: ai_reply}`，合并为 `[角色名] 回复` 返回

---

## 四、Persona 与 Runner 构建（personas.py）

### 4.1 Persona 列表

| id | 显示名 | 模型 | 工具 |
|----|--------|------|------|
| french_student_male | 法国学生（男） | ollama_chat/deepseek-r1:7b | french_student_female（AgentTool） |
| french_student_female | 法国学生（女） | ollama_chat/dolphin3:8b | french_student_male（AgentTool） |
| observer | 对话观察者 | ollama_chat/qwen3:4b-instruct | 无 |

### 4.2 Runner 构建流程

1. 为每个 persona 创建基础 Agent（无工具）
2. 用 `tools.register_agent_tool` 将每个 Agent 包装为 AgentTool
3. 法国男/女：各自 Agent 增加对方 AgentTool；Observer 不加工具
4. 为每个带工具的 Agent 创建 `InMemoryRunner`，`app_name = f"persona_{pid}"`

### 4.3 Session 映射

- `session_id = conversation_id`（同一会话内所有 persona 共用同一 conversation_id 作为 ADK session）
- `user_id = "godot"`：所有请求统一用户标识

---

## 五、辅助函数

| 函数 | 用途 |
|------|------|
| `_format_conversation_history` | 将 messages 转为 `"玩家: xxx\n角色: xxx"` 文本 |
| `_strip_thinking` | 移除 `<think>...</think>`、思考前缀等 |
| `_get_reply_from_events` | 从 ADK events 抽取 model 文本，去重、拼接、截断 |
| `_session_id` | 返回 conversation_id 或 `default_{persona_id}` |
| `_get_or_create_session` | 获取或创建 ADK session |
| `_generate_group_initial_messages` | 群聊开场：法国学生特殊流程，其他通用流程 |

---

## 六、REST API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /personas | 返回 persona 列表 |
| POST | /conversations | 创建会话，群聊时自动生成开场 |
| GET | /conversations | 会话列表（摘要） |
| GET | /conversations/{id} | 单会话详情（含消息） |
| GET | /conversations/{id}/messages | 消息列表（支持 limit、offset） |
| POST | /conversations/{id}/messages | 发送消息，返回本轮新增消息及合并 reply |

---

## 七、Godot 端要点

- **GameState**（Autoload）：`current_conversation_id`、`nearby_agents`、`last_ai_reply`、`last_player_message`
- **chat_interface_group.gd**：无会话时先 `POST /conversations`，有会话后 `POST /conversations/{id}/messages`
- **Dialogue Manager**：`npc_reply.dialogue`、`player_reply.dialogue` 通过 `{{ GameState.last_ai_reply }}`、`{{ GameState.last_player_message }}` 显示气泡
