# 两个法国学生自动对话设置

当 Player 同时进入两个法国学生（一男一女）的范围时，会自动触发初始对话（讨论 party 准备），然后玩家可以随时加入对话。

---

## 场景设置

1. **Agent1（法国学生男）**：
   - 节点名：如 `Agent1` 或 `FrenchStudentMale`
   - 挂脚本：`npc_persona_2d_group.gd`
   - Inspector 设置：
     - `persona_id` = `french_student_male`
     - `persona_name` = `法国学生（男）`
     - `is_french_student` = **true**（重要！）
   - 子节点：`Area2D + CollisionShape2D`

2. **Agent2（法国学生女）**：
   - 节点名：如 `Agent2` 或 `FrenchStudentFemale`
   - 挂脚本：`npc_persona_2d_group.gd`
   - Inspector 设置：
     - `persona_id` = `french_student_female`
     - `persona_name` = `法国学生（女）`
     - `is_french_student` = **true**（重要！）
   - 子节点：`Area2D + CollisionShape2D`

---

## 工作流程

1. **Player 进入范围**：
   - Player 先靠近 Agent1 → 单人模式，显示 Agent1 的名字
   - Player 再靠近 Agent2（或同时进入两个范围）→ 自动切换为群聊模式

2. **自动触发初始对话**：
   - 检测到两个法国学生都在范围内 → 自动调用 `POST /conversations` 创建会话（响应中含开场消息）
   - 后端会给两个 agent 一段法语提示（关于 party 准备），让他们开始讨论
   - 两个 agent 会各回复一轮，显示为：
     ```
     [法国学生（男）] 回复1
     
     [法国学生（女）] 回复2
     ```

3. **玩家加入对话**：
   - 玩家可以在任意时间发送消息
   - 消息会同时发给两个法国学生，两个都会回复
   - 回复格式：`[法国学生（男）] 回复\n\n[法国学生（女）] 回复`

---

## 后端配置

`personas.py` 已配置：
- `french_student_male`：使用 `qwen3:8b` 模型
- `french_student_female`：使用 `dolphin3:8b` 模型
- 两个 agent 的 instruction 都包含“讨论 party 准备”的上下文

后端通过 `POST /conversations` 创建会话时，若为两人及以上会生成开场消息；Godot 端在群聊首次进入时调用该接口即可：
- 检测到是两个法国学生时，会给法语初始提示
- 让两个 agent 开始对话，返回第一轮回复

---

## 注意事项

- 确保两个 Agent 的 `is_french_student` 都设为 **true**，否则不会触发自动对话
- 初始对话只触发一次（通过 `GameState.french_students_chat_started` 标记）
- 玩家离开范围后再进入，会重置标记，可再次触发初始对话
- 如果不想自动触发，可以把两个 Agent 的 `is_french_student` 设为 false，手动发送消息触发对话
