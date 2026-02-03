# 2D Top-down 版本快速搭建

目标：2D Top-down 游戏，Player 靠近 NPC 时切换 persona，支持单人/多人对话模式。

## 推荐场景树

```text
Node2D (Main2D)
├─ Floor (TileMap 或 StaticBody2D+CollisionShape2D 或 Sprite2D)
├─ Player (CharacterBody2D)  [挂 player_2d.gd]
├─ NPC_FrenchMale (Node2D)    [挂 npc_persona_2d.gd]
│  ├─ Sprite2D
│  └─ Area2D
│     └─ CollisionShape2D
├─ NPC_French ...
└─ ChatUI (CanvasLayer)
   └─ Control
      ├─ HTTPRequest
      ├─ SendButton
      ├─ ChatDisplay
      └─ InputBar
```

## 需要挂的脚本

- **Player**：`godot_2d_example/player_2d.gd`
- **每个 NPC 根节点**：`godot_2d_example/npc_persona_2d.gd`
  - `persona_id` / `persona_name` 按你的后端 `personas.py` 填（如 `french_student_male`、`french_student_female`、`observer`）。
  - `intro_dialogue` 可选：挂对应 `intro_*.dialogue`。

## 必要的 Autoload

在 **Project Settings → Autoload** 添加：
- `game_state_2d.gd`，Name 填 `GameState`

## 聊天 UI 脚本

建议直接复用你现在的 `godot_example/chat_interface.gd`（节点名保持一致：`HTTPRequest`、`SendButton`、`ChatDisplay`、`InputBar`）。

