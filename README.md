# Backend：多 Persona 聊天 API + Godot 2D Top-down 游戏

FastAPI 后端 + Google ADK，支持多个 AI persona（角色），供 Godot 2D Top-down 游戏调用。

---

## 项目结构

```
Backend/
├── Main.py                    # FastAPI 后端入口
├── personas.py               # Persona 配置（french_student_male, french_student_female, observer）
├── my_maori_agent/           # ADK Agent 示例（可参考）
├── godot_2d_example/        # 2D Top-down 游戏脚本和资源
│   ├── player_2d.gd         # 玩家移动脚本
│   ├── npc_persona_2d_group.gd  # NPC 脚本（支持群聊）
│   ├── chat_interface_group.gd  # 聊天 UI（支持单人/群聊）
│   ├── game_state_2d.gd     # 全局状态（Autoload）
│   └── dialogues/           # Dialogue Manager 对话文件
└── prompts/                  # Prompt 模板
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
- **场景**：参考 `godot_2d_example/README_2D_TOPDOWN.md` 和 `README_GROUP_CHAT.md`

---

## Persona 列表

- `french_student_male`：法国学生（男）（qwen3:8b）
- `french_student_female`：法国学生（女）（dolphin3:8b）
- `observer`：对话观察者（qwen3:4b-instruct，用于总结对话）

---

## API 端点

### RESTful（推荐：支持多会话与历史记录）

- `GET /personas`：获取所有可用 persona 列表
- `POST /conversations`：创建会话（body: `{"persona_ids": ["french_student_male"]}` 或多人 id 列表）；群聊且为两位法国学生时自动生成开场对话
- `GET /conversations`：获取会话列表（摘要）
- `GET /conversations/{id}`：获取单个会话详情（含消息历史）
- `GET /conversations/{id}/messages`：获取会话消息列表（支持 `limit`、`offset` 分页）
- `POST /conversations/{id}/messages`：在会话中发送一条消息（body: `{"content": "你好"}`），返回本轮新增消息及合并回复

### 兼容旧版 Godot（仍可用）

- `POST /chat`：发送消息（行为与之前一致，内部使用 default 会话）
- `POST /chat/start_group`：触发群聊开场（内部创建 default 会话并生成开场）

---

## 功能特性

- ✅ 单人对话：Player 靠近一个 NPC
- ✅ 多人对话（群聊）：Player 同时靠近两个或更多 NPC
- ✅ 自动触发：两个法国学生进入范围时自动开始讨论 party 准备
- ✅ 对话总结：Observer persona 可总结对话历史

---

## 文档

- `godot_2d_example/README_2D_TOPDOWN.md`：2D Top-down 快速搭建
- `godot_2d_example/README_GROUP_CHAT.md`：群聊功能说明
- `godot_2d_example/README_FRENCH_STUDENTS.md`：法国学生自动对话设置
- `godot_2d_example/README_OBSERVER.md`：Observer 使用说明
