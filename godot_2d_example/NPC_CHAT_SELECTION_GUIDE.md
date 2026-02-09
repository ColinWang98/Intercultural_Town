# NPC 对话选择系统使用指南

## 📋 概述

这个系统允许 NPC agent 选择其他 NPC 作为聊天对象，支持：
- **自动模式**：玩家靠近时，自动检测附近 NPC 并提示
- **手动模式**：玩家主动选择哪些 NPC 对话
- **动态组合**：可以任意选择 2+ 个 NPC 进行群聊

---

## 🎮 使用方法

### 方式 1：自动检测模式（推荐）

#### 1. 设置 NPC 节点

```
SceneRoot (Node2D)
├─ NPC1 (Node2D)
│   ├─ Sprite2D
│   ├─ CollisionShape2D
│   ├─ Area2D
│   └─ npc_persona_interactive.gd
│       ├─ persona_id: "mikko"
│       ├─ persona_name: "Mikko"
│       └─ chat_mode: "Auto"
│
├─ NPC2 (Node2D)
│   ├─ Sprite2D
│   ├─ CollisionShape2D
│   ├─ Area2D
│   └─ npc_persona_interactive.gd
│       ├─ persona_id: "mark"
│       ├─ persona_name: "Mark"
│       └─ chat_mode: "Auto"
│
└─ Player (CharacterBody2D)
```

#### 2. 在 Inspector 中配置

```
NPC1 Inspector:
├─ Script: npc_persona_interactive.gd
├─ Persona Id: mikko
├─ Persona Name: Mikko
└─ Chat Mode: Auto

NPC2 Inspector:
├─ Script: npc_persona_interactive.gd
├─ Persona Id: mark
├─ Persona Name: Mark
└─ Chat Mode: Auto
```

#### 3. 运行时行为

1. **玩家单独靠近 NPC1** → 单人对话模式
2. **玩家同时靠近 NPC1 + NPC2** → 显示提示："按 E 选择对话对象"
3. **玩家按 E** → 打开对话选择 UI
4. **选择要对话的 NPC** → 开始群聊

---

### 方式 2：手动选择模式

#### 配置

```
NPC Inspector:
├─ Chat Mode: Manual
└─ Show Chat Indicator: true
```

#### 行为

1. 玩家靠近 NPC → 显示"选择对话"按钮
2. 点击按钮 → 打开 NPC 选择列表
3. 勾选要对话的 NPC → 点击"开始对话"

---

### 方式 3：完全手动触发

#### 代码中触发

```gdscript
# 获取 NPC 引用
var npc1 = get_node("NPC1")
var npc2 = get_node("NPC2")

# 手动发起对话
npc1._start_group_chat(["mikko", "mark"])
```

---

## 🔧 NPC 检测配置

### 检测范围

默认情况下，NPC 会在 **150 像素**范围内检测其他 NPC。可以在代码中调整：

```gdscript
# 在 _find_nearby_npcs() 函数中
if distance <= 150.0:  # 修改这个值
```

### 碰撞层设置

确保 NPC 在正确的碰撞层：

```gdscript
# 在 _setup_npc_detection() 中
_detection_area.collision_layer = 0
_detection_area.collision_mask = 4  # NPC 在第 4 层
```

**Godot 项目设置**：
```
项目设置 → Layer Names → 2D Physics:
- Layer 1: "player"
- Layer 2: "walls"
- Layer 3: "npcs"
- Layer 4: "npc_detection"
```

---

## 🎨 UI 自定义

### 修改提示文本

```gdscript
# 在 _show_chat_prompt() 中
_chat_prompt_label.text = "按 E 选择对话对象"  # 修改这里
```

### 修改按钮样式

```gdscript
# 在 _show_manual_chat_button() 中
_chat_button.text = "选择对话"  # 修改按钮文本
_chat_button.custom_minimum_size = Vector2(80, 30)  # 修改大小
```

---

## 📊 与现有系统集成

### 与 `game_state_2d.gd` 配合

这个系统完全兼容现有的 `game_state_2d.gd`：

```gdscript
# GameState 会自动管理
- nearby_agents: 附近的 agent 列表
- current_conversation_id: 当前会话 ID
- group_chat_started: 是否已触发群聊
```

### 与动态 persona 配合

可以在运行时传递动态 persona 信息：

```gdscript
var dynamic_personas = [
    {
        "id": "mark",
        "name": "Mark",
        "personality": "热情的美国人",
        "personality_type": "Extrovert",
        "likes": ["篮球", "健身"],
        "interests": "运动",
        "speaking_style": "充满活力"
    }
]

# 修改 _start_group_chat() 以支持动态 persona
func _start_group_chat(persona_ids: Array[String]) -> void:
    var payload = {
        "persona_ids": persona_ids,
        "dynamic_personas": dynamic_personas
    }
    # ... 发送请求
```

---

## 🎯 完整示例场景

### 场景：校园广场

```
校园广场 (Node2D)
├─ 学生A (NPC1)
│   └─ npc_persona_interactive.gd
│       ├─ persona_id: "alice"
│       ├─ persona_name: "Alice"
│       └─ chat_mode: "Auto"
│
├─ 学生B (NPC2)
│   └─ npc_persona_interactive.gd
│       ├─ persona_id: "bob"
│       ├─ persona_name: "Bob"
│       └─ chat_mode: "Auto"
│
├─ 学生C (NPC3)
│   └─ npc_persona_interactive.gd
│       ├─ persona_id: "charlie"
│       ├─ persona_name: "Charlie"
│       └─ chat_mode: "Auto"
│
└─ 玩家 (Player)
```

### 交互流程

1. **玩家走到学生A 附近**
   → 单人对话模式，可以和 A 1v1 对话

2. **玩家走到学生A + 学生B 附近**
   → 提示："按 E 选择对话对象"
   → 按 E 打开选择器

3. **选择器显示**
   ```
   ┌─────────────────────┐
   │  选择对话对象         │
   ├─────────────────────┤
   │ ☐ Alice (自己)      │
   │ ☑ Bob               │
   │ ☐ Charlie           │
   ├─────────────────────┤
   │   [开始对话] [取消]  │
   └─────────────────────┘
   ```

4. **选择 Alice + Bob**
   → 后端创建 Alice + Bob 的对话
   → 显示两人的开场对话

5. **选择 Alice + Bob + Charlie**
   → 创建三人群聊
   → 三个 NPC 轮流发言

---

## 🚀 高级用法

### 1. NPC 主动发起对话

```gdscript
# NPC 可以主动走向其他 NPC 并发起对话
func _on_timer_timeout():
	var nearby = _find_nearby_npcs()
	if nearby.size() > 0:
		# 随机选择一个
		var target = nearby.pick_random()
		initiate_chat_with([target["persona_id"]])
```

### 2. 基于距离的智能选择

```gdscript
func get_suggested_chat_partners() -> Array[String]:
	"""建议对话对象（距离最近的 2 个）"""
	var nearby = _find_nearby_npcs()
	nearby.sort_custom(func(a, b): return a["distance"] < b["distance"])

	var partners = [persona_id]
	for i in min(1, nearby.size()):
		partners.append(nearby[i]["persona_id"])

	return partners
```

### 3. 基于性格的匹配

```gdscript
func get_compatible_partners() -> Array[String]:
	"""根据性格选择兼容的对话对象"""
	var my_personality = "Extrovert"  # 从配置获取
	var nearby = _find_nearby_npcs()

	var compatible = []
	for npc in nearby:
		var their_personality = npc["node"].get("personality_type", "Ambivert")
		# Extrovert 可以和任何人对话
		if my_personality == "Extrovert":
			compatible.append(npc["persona_id"])

	return compatible
```

---

## ⚠️ 注意事项

1. **性能考虑**
   - NPC 互相检测会频繁调用
   - 建议限制检测范围和频率
   - 可以使用定时器而不是 `_process`

2. **网络请求**
   - 每次对话都会调用后端 API
   - 避免在短时间内重复请求
   - 使用 `group_chat_started` 标志防止重复

3. **UI 管理**
   - 确保正确清理 UI 节点
   - 使用 `queue_free()` 而不是 `free()`
   - 场景切换时清理所有 UI

---

## 🔧 调试

### 查看附近的 NPC

```gdscript
func _debug_print_nearby():
	print(f"[{persona_name}] 附近的 NPC:")
	for npc in _find_nearby_npcs():
		print(f"  - {npc['persona_name']} ({npc['distance']}px)")
```

### 查看对话状态

```gdscript
var gs = get_node_or_null("/root/GameState")
print("当前对话 ID:", gs.get_conversation_id())
print("附近 agents:", gs.nearby_agents)
```

---

## 📝 TODO 功能

可以进一步扩展的功能：

- [ ] NPC 之间的好感度系统
- [ ] 对话历史记录
- [ ] NPC 记住之前的对话
- [ ] 基于场景的对话主题
- [ ] NPC 移动到对话位置
- [ ] 对话结束后的表情和动作
