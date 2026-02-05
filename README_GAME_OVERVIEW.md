## Godot 2D Top-down + FastAPI/ADK 项目总览

本项目是一个 **2D Top-down Godot 游戏 + FastAPI 后端** 的多 persona 聊天 Demo：  
玩家在 Godot 场景中移动，靠近不同 NPC，与其单聊或群聊；NPC 的回复由 Python FastAPI + Google ADK + LiteLlm + Ollama 提供。

---

## 1. 整体架构

- **后端**：`FastAPI + Google ADK + LiteLlm + Ollama`
  - 提供 REST API：`GET /personas`、`POST/GET /conversations`、`GET/POST /conversations/{id}/messages`
  - 每个 persona 独立一个 ADK Agent + Runner + Session
- **前端**：`Godot 4 2D`
  - 使用 `HTTPRequest` 调用 FastAPI 接口
  - `game_state_2d.gd` 作为 Autoload `GameState`，统一管理“当前对话对象”和群聊状态
  - `chat_interface_group.gd` 负责聊天 UI + HTTP 请求

主要目标：

- 玩家靠近一个 NPC → 与该 NPC 对话（单人模式）
- 玩家同时靠近两个或以上 NPC → 进入群聊模式，后端对每个 persona 生成回复并合并显示
- 两位法国学生在群聊模式下会自动以“party 准备”为主题互相对话

---

## 2. 后端服务

### 2.1 `personas.py`：Persona 配置与 Runner 构建

**作用**：集中管理 persona 配置，并为每个 persona 创建一个 ADK `Agent + InMemoryRunner`。

- 全局设置：
  - `_LANG`：统一要求所有 persona **用中文回复**，可适当夹杂本国语言词汇。
  - `_NO_COT`：统一要求 **不要输出思考过程 / 推理 / `<think>...</think>`**，只输出要对玩家说的话。

- 当前 personas：
  - `french_student_male`（法国学生·男）
    - 模型：`ollama_chat/qwen3:8b`
    - 人设：外向、热情、爱组织活动；和女学生讨论 party 准备（食材、场地等）。
    - 风格：常用 “Alors”、“D'accord”、“C'est bon” 等法语词。
    - 指令拼接：`"""...""" + _NO_COT + _LANG`
  - `french_student_female`（法国学生·女）
    - 模型：`ollama_chat/dolphin3:8b`
    - 人设：细心、有条理、喜欢规划细节；和男学生讨论 party 准备。
    - 风格：常用 “D'accord”、“Peut-être”、“Il faut” 等法语词。
    - 同样拼接 `_NO_COT + _LANG`
  - `observer`（对话观察者）
    - 模型：`ollama_chat/qwen3:4b-instruct`
    - 人设：只负责**客观总结玩家与各 Agent 的对话**，不参与对话、不给建议。
    - 输出结构：`对话概览 / 关键信息 / 情绪与关系 / 未解决问题`

- Runner 构建：
  - `_build_runners()` 遍历 `PERSONAS`：
    - 为每个 persona 创建 `Agent(model=info["model"], instruction=info["instruction"])`
    - 创建 `InMemoryRunner(agent=agent, app_name=f"persona_{pid}")`
  - 全部 Runner 存在全局 `RUNNERS` 中供后端使用。

### 2.2 `Main.py`：FastAPI 接口与对话逻辑

基础：

- `USER_ID = "godot"`：所有请求的用户 ID。
- `DEFAULT_PERSONA = "french_student_male"`：默认 persona。
- `MAX_REPLY_LENGTH = 2000`：最大回复长度，避免过长导致前端卡顿。

核心辅助函数：

- `_strip_thinking(text: str) -> str`：
  - 删除输出中的 `<think>...</think>` 片段，防止“思考过程”被玩家看到。
- `_get_reply_from_events(events)`：
  - 从 ADK events 中抽取 `role == "model"` 的文本部分。
  - 对每一块文本去重（防止模型重复）、拼接、截断长度。
  - 最后调用 `_strip_thinking` 清洗，再返回。
- `_session_id(persona_id: str) -> str`：
  - 返回 `f"default_{persona_id}"`，保证**每个 persona 有独立会话历史**。
- `_get_or_create_session(runner, app_name, session_id)`：
  - 若 session 不存在则创建，否则直接读取。

暴露的 API（REST）：

- `GET /personas`
  - 返回形如 `[{ "id": "french_student_male", "name": "法国学生（男）" }, ...]`
  - 前端可用于下拉选择或按钮展示。

- `POST /conversations`
  - 请求体：`{"persona_ids": ["french_student_male"]}` 或多人 id 列表。
  - 创建新会话，返回 `ConversationItem`（含 `id`、`persona_ids`、`messages`、`created_at`）。
  - 若 `persona_ids` 为两人及以上（群聊），后端自动生成开场消息并写入 `messages`（两位法国学生时按 party 准备场景互相对话）。

- `GET /conversations`、`GET /conversations/{id}`、`GET /conversations/{id}/messages`
  - 列会话摘要、取单会话详情、取会话消息（支持 `limit`、`offset`）。

- `POST /conversations/{id}/messages`
  - 请求体：`{"content": "你好"}`。
  - 在指定会话中追加用户消息，调用各 persona 的 Runner 生成回复并追加到会话；返回本轮新增的 `messages` 及合并后的 `reply`。

---

## 3. Godot 2D 示例（`godot_2d_example/`）

目录关键文件：

- `player_2d.gd`：玩家移动（Top-down，WASD / 方向键）。
- `npc_persona_2d.gd`：单人对话 NPC。
- `npc_persona_2d_group.gd`：支持群聊的 NPC。
- `game_state_2d.gd`：全局 GameState（Autoload）。
- `chat_interface_group.gd`：聊天 UI（支持单人/群聊）。
- `dialogues/`：
  - `npc_reply.dialogue`：AI 回复气泡对话资源。
  - `player_reply.dialogue`：玩家发言气泡对话资源。

### 3.1 全局 GameState（`game_state_2d.gd`）

在 Project Settings → Autoload 中添加，Name = `GameState`。

主要字段：

- `current_persona_id: String`
  - 0 个 NPC 时：默认 `"french_student_male"`
  - 1 个 NPC 时：设为该 NPC 的 persona_id
  - ≥2 个 NPC 时：设为 `"group"`（用于标记群聊）
- `current_persona_name: String`
  - 0 个：默认 `"法国学生（男）"`
  - 1 个：NPC 名称
  - ≥2 个：`"A & B & C"` 拼接
- `nearby_agents: Dictionary`
  - 键：`persona_id`
  - 值：`persona_name`
- `group_chat_started: bool`
  - 是否已经触发过**本轮群聊的开场**（防止重复创建会话或重复请求开场）。
- `last_ai_reply: String`
  - 最近一条 AI 回复内容，给 Dialogue Manager 的 `.dialogue` 使用（`{{ GameState.last_ai_reply }}`）。
- `last_player_message: String`
  - 最近一条玩家发言（如“你 → [群聊]: xxx”），同样给气泡用。

主要方法：

- `add_nearby_agent(persona_id, persona_name)` / `remove_nearby_agent(persona_id)`：
  - NPC 碰撞区域内外切换时调用，并触发 `_update_current_persona()`。
- `_update_current_persona()`：
  - 根据 `nearby_agents.size()` 更新 `current_persona_*` 与 `group_chat_started`。
- `is_group_chat() -> bool`：
  - 当 `nearby_agents.size() >= 2` 时为真。
- `get_nearby_persona_ids() -> Array[String]`：
  - 返回当前范围内所有 persona_id。

### 3.2 单人 NPC（`npc_persona_2d.gd`）

- 挂在单个 NPC 的根 `Node2D` 上，子树中需包含 `Area2D + CollisionShape2D`。
- 玩家进入 `Area2D` 时：
  - 调用 `GameState.set_nearby_npc(persona_id, persona_name)`。
  - 可选：通过 Dialogue Manager 播放 `intro_dialogue` 作为招呼。
- 玩家离开时：
  - 关闭招呼气泡（如启用），并 `GameState.clear_nearby_npc()`。

### 3.3 群聊 NPC（`npc_persona_2d_group.gd`）

用于支持“多人范围 → 群聊模式”的 NPC。

导出变量：

- `persona_id: String`
- `persona_name: String`
- `intro_dialogue: Resource`（可选，靠近时的招呼）
- `intro_title: String = "start"`
- `close_balloon_on_exit: bool = true`
- `is_french_student: bool`（主要用于你在 Inspector 里标记，逻辑上不再强依赖）

关键逻辑：

- `_on_body_entered(body)`：
  1. 玩家进入某个 NPC 范围：
     - `GameState.add_nearby_agent(persona_id, persona_name)`
  2. 若此时已满足群聊条件（`GameState.is_group_chat()` 为真）：
     - 读取 `GameState.group_chat_started`，若是 **false**：
       - 设为 `true`
       - 获取 `nearby_ids = GameState.get_nearby_persona_ids()`
       - 调用 `_try_start_group_chat(nearby_ids)` → 后端 `POST /conversations`（创建会话并拿到含开场的 messages）
       - `return`，不再播普通 intro_dialogue，直接以群聊开场代替
  3. 若仍是单人模式：调用 `_try_show_intro_balloon()` 播招呼。

- `_on_body_exited(body)`：
  - 关闭 intro 气泡（如有），并 `GameState.remove_nearby_agent(persona_id)`。
  - 是否重置 `group_chat_started` 交由 `GameState._update_current_persona()` 统一处理。

- `_try_start_group_chat(persona_ids)`：
  - 创建临时 `HTTPRequest`，POST `{"persona_ids": persona_ids}` 到 `http://127.0.0.1:8000/conversations`。
  - 收到会话响应（含 `id`、`messages`）后：将 `id` 存到 `GameState`，若有开场 `messages` 则取最后一条或合并为 `last_ai_reply`，并用 Dialogue Manager 气泡展示。

### 3.4 聊天 UI（`chat_interface_group.gd`）

挂在一个 `Control` 节点下，节点结构推荐：

- `Control`（挂脚本）
  - `HTTPRequest`
  - `SendButton`
  - `ChatDisplay`（`RichTextLabel`，可选）
  - `InputBar`（通常是 `TextEdit`）
  - `CurrentPersonaLabel`（`Label`，可选）

功能：

- 初始化：
  - 启用 `ChatDisplay.bbcode_enabled` 与 `scroll_following`。
  - `InputBar`（TextEdit）支持：
    - Enter 发送
    - Shift+Enter 换行

- 显示当前对话对象：
  - `_process(delta)` 中根据 `GameState`：
    - 单人：`"当前: {persona_name}"`
    - 群聊：`"当前: [群聊] {persona_name}"`（如 `"法国学生（男） & 法国学生（女）"`）

- 发送消息：
  - 从 `InputBar` 取文本，构造玩家发言字符串：
    - 群聊：`"你 → [群聊]: %s"`
    - 单人：`"你 → {当前 persona_name}: {文本}"`
  - 尝试用 `player_reply_dialogue` + Dialogue Manager 气泡显示；必要时回退写入 `ChatDisplay`。
  - 调用 `_send_to_backend(message)` 发起 HTTP 请求。

- `_send_to_backend(message)`（REST 流程）：
  - 若当前无 `GameState.current_conversation_id`：先 `POST /conversations`（body: `{"persona_ids": [...]}`，从 `GameState.get_nearby_persona_ids()` 或当前单人 id 取得），拿到 `id` 后存到 GameState，再 `POST /conversations/{id}/messages`（body: `{"content": message}`）。
  - 若已有 `current_conversation_id`：直接 `POST /conversations/{id}/messages`（body: `{"content": message}`）。
  - 请求地址：`http://127.0.0.1:8000/conversations`、`http://127.0.0.1:8000/conversations/{id}/messages`。

- 处理回复：
  - 解析 JSON，若含 `"reply"`（或新消息列表）：
    - 写入 `GameState.last_ai_reply` 并尝试气泡显示。
    - 若未设置“仅气泡”或气泡失败，则在 `ChatDisplay` 中展示蓝色“回复”行。

---

## 4. 运行与使用

1. **启动后端**
   - 在仓库根目录执行：
     - `python Main.py`
   - 确保 Ollama 在 `http://localhost:11434` 运行，且所需模型已 `pull`。

2. **配置 Godot**
   - 在 Project Settings → Autoload：
     - 添加 `godot_2d_example/game_state_2d.gd`，Name 填 `GameState`。
   - 场景中：
     - 玩家节点 `Player (CharacterBody2D)` 挂 `player_2d.gd`。
     - NPC：
       - 只需要单人对话时：挂 `npc_persona_2d.gd`。
       - 需要群聊功能时：挂 `npc_persona_2d_group.gd`。
     - 聊天 UI：
       - 建一个 `CanvasLayer/Control`，挂 `chat_interface_group.gd`，并按照脚本期望的子节点命名好控件。

3. **实际体验**
   - 玩家靠近某个 NPC → 屏幕上显示当前对话对象，输入框可发送消息，与该 persona 对话。
   - 玩家同时进入两个或更多 NPC 的范围 → `GameState` 切换为群聊模式：
     - 首次发消息前会先 `POST /conversations` 创建会话，响应中已包含开场消息（两位法国学生时按 party 场景自动对话）。
     - 后续玩家发送的消息会同时发给所有范围内的 persona，每个都会单独回复，前端以 `[角色名] 回复` 的形式合并显示。

---

这份文档是对当前 Godot + FastAPI/ADK 项目结构与行为的总览说明，后续如果你扩展新的 persona、加入新地图或 UI，只需按这里的结构增加对应脚本/配置即可。  
