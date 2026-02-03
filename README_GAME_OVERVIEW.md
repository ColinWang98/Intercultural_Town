## Godot 2D Top-down + FastAPI/ADK 项目总览

本项目是一个 **2D Top-down Godot 游戏 + FastAPI 后端** 的多 persona 聊天 Demo：  
玩家在 Godot 场景中移动，靠近不同 NPC，与其单聊或群聊；NPC 的回复由 Python FastAPI + Google ADK + LiteLlm + Ollama 提供。

---

## 1. 整体架构

- **后端**：`FastAPI + Google ADK + LiteLlm + Ollama`
  - 提供 REST API：`/personas`、`/chat`、`/chat/start_group`
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

暴露的 API：

- `GET /personas`
  - 返回形如 `[{ "id": "french_student_male", "name": "法国学生（男）" }, ...]`
  - 前端可用于下拉选择或按钮展示。

- `POST /chat`
  - 请求体 `ChatReq`：
    - `user_input: str`
    - `persona: str | list[str]`（单人或群聊）
  - 处理流程：
    1. 将 `persona` 正规化：
       - 若是数组：`strip().lower()` 后过滤空字符串，若为空则使用 `DEFAULT_PERSONA`。
       - 若是字符串：`(req.persona or "").strip().lower()`，为空则用默认。
    2. 校验 persona 是否存在于 `personas.PERSONAS`，不存在则返回错误提示。
    3. **多人（群聊）**：
       - 遍历 persona_ids：
         - 为每个 persona 取对应 `RUNNER` 与 session。
         - 构造群聊上下文：当前参与的角色名列表 + 自己的 persona 名。
         - prompt 形如：  
           `【群聊模式】现在有 N 位角色在对话：A, B, ...。你是 X，... 玩家说：{user_input}`
         - 调用 `runner.run_async(...)` 获取每个角色的回复。
         - 每条回复包装为 `[角色显示名] 内容`。
       - 最终用 `\n\n` 拼接所有回复返回。
    4. **单人**：
       - 对目标 persona 的 Runner 直接发送 `user_input`，获取单条回复返回。

- `POST /chat/start_group`
  - 用于**群聊开场**，在玩家刚刚进入“多人范围”时由前端触发。
  - 请求体 `StartGroupChatReq`：
    - `persona_ids: list[str]`
  - 逻辑：
    1. 少于 2 个 persona 则返回错误。
    2. 校验 persona 是否存在。
    3. 特判 **两个法国学生**：
       - 构造法语场景提示 `initial_prompt_fr`（讨论 party 准备的内容）。
       - 先给男学生发送场景提示，得到初始发言 A。
       - 再把 A 作为“对方说：A”拼入给女学生的 prompt，引导她接话。
    4. 其他任意组合：
       - 对每个 persona 发送群聊开场 context（说明参与者是谁，让其以自身角色身份开始对话）。
    5. 将所有开场发言按 `[角色名] 回复` 拼接成一个字符串返回。

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
  - 是否已经触发过**本轮群聊的开场**（防止重复调用 `/chat/start_group`）。
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
       - 调用 `_try_start_group_chat(nearby_ids)` → 后端 `/chat/start_group`
       - `return`，不再播普通 intro_dialogue，直接以群聊开场代替
  3. 若仍是单人模式：调用 `_try_show_intro_balloon()` 播招呼。

- `_on_body_exited(body)`：
  - 关闭 intro 气泡（如有），并 `GameState.remove_nearby_agent(persona_id)`。
  - 是否重置 `group_chat_started` 交由 `GameState._update_current_persona()` 统一处理。

- `_try_start_group_chat(persona_ids)`：
  - 创建一个临时 `HTTPRequest` 节点。
  - POST `{"persona_ids": persona_ids}` 到 `http://127.0.0.1:8000/chat/start_group`。
  - 收到 `{ "reply": "..." }` 后：
    - 写入 `GameState.last_ai_reply`。
    - 若有 `DialogueManager` 且存在可用的 `npc_reply.dialogue`，用气泡展示这段群聊开场。

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

- `_send_to_backend(message)`：
  - 通过 `GameState.get_nearby_persona_ids()` 获取当前范围内 persona IDs。
  - 构造 `persona` 字段：
    - 若 `persona_ids.size() > 1`：用数组（群聊）。
    - 若 `persona_ids.size() == 1`：用单个字符串。
    - 若为 0：回退 `_get_active_persona_id()`（极端兜底）。
  - 发送到 `POST http://127.0.0.1:8000/chat`。

- 处理回复：
  - 解析 JSON，若含 `"reply"`：
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
     - 自动调用 `/chat/start_group` 生成开场对话（两位法国学生会按 party 场景自动对话）。
     - 后续玩家发送的消息会同时发给所有范围内的 persona，每个都会单独回复，前端以 `[角色名] 回复` 的形式合并显示。

---

这份文档是对当前 Godot + FastAPI/ADK 项目结构与行为的总览说明，后续如果你扩展新的 persona、加入新地图或 UI，只需按这里的结构增加对应脚本/配置即可。  
