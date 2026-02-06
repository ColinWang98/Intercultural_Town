# Backend：多 Persona 聊天 API + Godot 2D Top-down 游戏

FastAPI 后端 + Google ADK，支持多个 AI persona（角色），供 Godot 2D Top-down 游戏调用。

---

## 项目结构

```
Backend/
├── Main.py                    # FastAPI 后端入口（REST）
├── personas.py                # Persona 配置与 ADK Agent/Runner 构建
├── tools.py                   # AgentTool 注册与缓存（法国学生互问工具）
├── my_maori_agent/            # ADK Agent 示例（可参考，非运行时依赖）
├── godot_2d_example/          # 2D Top-down 游戏脚本与资源
│   ├── player_2d.gd           # 玩家移动
│   ├── npc_persona_2d.gd      # 单人 NPC 脚本
│   ├── npc_persona_2d_group.gd # NPC 脚本（支持群聊、开场对话）
│   ├── chat_interface_group.gd # 聊天 UI（REST 会话、Dialogue Manager 气泡）
│   ├── game_state_2d.gd       # 全局状态（Autoload：GameState）
│   └── dialogues/             # Dialogue Manager：npc_reply.dialogue、player_reply.dialogue
└── godot_example/             # 旧版单人聊天示例（需改为使用 REST：POST /conversations、POST .../messages，或直接使用 godot_2d_example）
```

---

## 快速开始

### 1. 后端启动

```bash
# 确保 Ollama 运行在 localhost:11434
python Main.py
# 或
adk web --port 8000
```

### 2. Godot 项目设置

- **Autoload**：添加 `godot_2d_example/game_state_2d.gd`，Name = `GameState`
- **场景**：参考 `godot_2d_example/README_2D_TOPDOWN.md`、`README_FRENCH_STUDENTS.md`、`README_OBSERVER.md`

---

## Persona 列表

- `french_student_male`：法国学生（男）（Ollama：deepseek-r1:7b，可调用 french_student_female 工具）
- `french_student_female`：法国学生（女）（Ollama：dolphin3:8b，可调用 french_student_male 工具）
- `observer`：对话观察者（Ollama：qwen3:4b-instruct，用于客观总结对话，无工具）

---

## API 端点

### RESTful（推荐：支持多会话与历史记录）

- `GET /personas`：获取所有可用 persona 列表
- `POST /conversations`：创建会话（body: `{"persona_ids": ["french_student_male"]}` 或多人 id 列表）；群聊且为两位法国学生时自动生成开场对话
- `GET /conversations`：获取会话列表（摘要）
- `GET /conversations/{id}`：获取单个会话详情（含消息历史）
- `GET /conversations/{id}/messages`：获取会话消息列表（支持 `limit`、`offset` 分页）
- `POST /conversations/{id}/messages`：在会话中发送一条消息（body: `{"content": "你好"}`），返回本轮新增消息及合并回复

**说明**：后端会对模型输出做思考标签过滤（`<think>` 等）与长度截断（单次回复上限 2000 字符），Godot 端使用 REST 时需在项目设置中配置 Dialogue Manager 的 Balloon Path，并将 `game_state_2d.gd` 设为 Autoload `GameState`。

---

## 功能特性

- ✅ 单人对话：Player 靠近一个 NPC
- ✅ 多人对话（群聊）：Player 同时靠近两个或更多 NPC
- ✅ 自动触发：两个法国学生进入范围时自动开始讨论 party 准备
- ✅ 对话总结：Observer persona 可总结对话历史

---


---

## 文档

- `README_ARCHITECTURE.md`：项目逻辑架构（数据流、编排逻辑、模块职责）
- `README_GAME_OVERVIEW.md`：整体架构与后端/前端说明
- `godot_2d_example/README_2D_TOPDOWN.md`：2D Top-down 场景与节点搭建
- `godot_2d_example/README_FRENCH_STUDENTS.md`：法国学生与群聊、开场对话设置
- `godot_2d_example/README_OBSERVER.md`：Observer 使用说明
