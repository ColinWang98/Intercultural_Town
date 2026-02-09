# 动态 Persona 系统 - 架构说明

## 概述

后端已完全支持动态 Persona 系统，允许在前端（Godot）创建任意自定义角色，无需修改后端代码。

---

## 架构简化

### 移除的组件
- ❌ `religion_expert` - 宗教禁忌专家
- ❌ `allergy_expert` - 食物过敏专家
- ❌ 复杂的状态机（religion_deep, allergy_deep, wrap_up）

### 保留的组件
- ✅ `mikko` - 芬兰学生 Mikko（外向热情）
- ✅ `aino` - 芬兰学生 Aino（细心有条理）
- ✅ `observer` - 对话观察者（总结+鼓励）
- ✅ **动态 Persona 系统** - 支持任意自定义角色

---

## 状态机（简化版）

```
small_talk (闲聊)
    ↓ [玩家说"再见"/"好了"/"结束"]
finished (完成 + Observer 总结)
```

**特点：**
- 2 个简单状态
- 无复杂的状态转换
- 支持多人同时对话

---

## API 使用

### 创建会话（POST /conversations）

```json
{
  "persona_ids": ["mikko", "aino", "custom_expert"],
  "dynamic_personas": [
    {
      "id": "custom_expert",
      "name": "饮食专家",
      "gender": "Female",
      "personality": "专业、友善、有耐心",
      "personality_type": "Extrovert",
      "interests": "营养学、健康管理、饮食文化",
      "speaking_style": "温和专业",
      "likes": ["帮助他人", "健康饮食"],
      "dislikes": ["不健康的饮食习惯"],
      "current_state": "准备讨论聚餐",
      "location_hint": "活动室"
    }
  ]
}
```

### 发送消息（POST /conversations/{id}/messages）

```json
{
  "content": "我们聚餐需要考虑哪些饮食禁忌？"
}
```

---

## 动态 Persona 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 唯一标识符（任意 ID） |
| `name` | string | ✅ | 显示名称 |
| `gender` | string | ❌ | 性别（默认 "Male"） |
| `personality` | string | ❌ | 性格描述 |
| `personality_type` | string | ❌ | 性格类型（默认 "Extrovert"） |
| `interests` | string | ❌ | 兴趣爱好 |
| `speaking_style` | string | ❌ | 说话风格 |
| `likes` | list[str] | ❌ | 喜欢的事物 |
| `dislikes` | list[str] | ❌ | 不喜欢的事物 |
| `current_state` | string | ❌ | 当前状态 |
| `location_hint` | string | ❌ | 位置提示 |

---

## Godot 集成

### agent_interactive.gd 配置

```gdscript
@export var persona_id: String = "my_custom_agent"
@export var persona_name: String = "我的自定义角色"

@export var use_dynamic_persona: bool = true
@export var personality: String = "开朗友善"
@export var interests: String = "科技、游戏、音乐"
@export var speaking_style: String = "轻松幽默"
```

### 构建动态 Persona

```gdscript
func _build_dynamic_persona() -> Dictionary:
    return {
        "id": get_persona_id(),
        "name": get_persona_name(),
        "gender": get_gender(),
        "personality": personality,
        "interests": interests,
        "speaking_style": speaking_style,
        # ... 其他字段
    }
```

---

## 多人对话支持

系统现在支持：
- ✅ 2+ 个预定义 personas（mikko + aino）
- ✅ 混合预定义和动态 personas
- ✅ 全部使用动态 personas
- ✅ 任意数量的参与者

### 示例场景

**场景 1：芬兰学生 + 自定义专家**
```json
{
  "persona_ids": ["mikko", "aino", "nutrition_expert"],
  "dynamic_personas": [
    { "id": "nutrition_expert", "name": "营养师", ... }
  ]
}
```

**场景 2：完全自定义**
```json
{
  "persona_ids": ["teacher", "student", "parent"],
  "dynamic_personas": [
    { "id": "teacher", "name": "王老师", ... },
    { "id": "student", "name": "小明", ... },
    { "id": "parent", "name": "李妈妈", ... }
  ]
}
```

---

## 后端 Persona 列表

| Persona ID | 名称 | 说明 |
|------------|------|------|
| `mikko` | Mikko | 芬兰学生（外向热情） |
| `aino` | Aino | 芬兰学生（细心有条理） |
| `observer` | 对话观察者 | 总结对话 + 鼓励性反馈 |

**注意：** 其他任何 persona_id 都可以通过 `dynamic_personas` 参数动态注册！

---

## 迁移指南

### 如果之前使用了专家 personas

**旧代码（不再支持）：**
```json
{
  "persona_ids": ["mikko", "aino", "religion_expert", "allergy_expert"]
}
```

**新代码（使用动态 persona）：**
```json
{
  "persona_ids": ["mikko", "aino", "religion_expert", "allergy_expert"],
  "dynamic_personas": [
    {
      "id": "religion_expert",
      "name": "宗教专家",
      "personality": "专业、友善",
      "interests": "宗教文化、饮食禁忌",
      "speaking_style": "温和耐心"
    },
    {
      "id": "allergy_expert",
      "name": "过敏专家",
      "personality": "细心、专业",
      "interests": "食品安全、营养健康",
      "speaking_style": "专业清晰"
    }
  ]
}
```

---

## 验证清单

- [x] personas.py - 移除专家 personas
- [x] Main.py - 简化状态机
- [x] Main.py - 移除 _expert_respond 函数
- [x] Main.py - 移除 _detect_focus_flags 函数
- [x] 动态 persona API 完整支持
- [x] 多人对话测试通过

---

## 下一步

1. **在 Godot 中创建自定义 Agent**
   - 设置 `persona_id` 为任意值
   - 配置动态 persona 属性
   - 测试多人对话

2. **验证后端**
   ```bash
   # 启动后端
   python Main.py

   # 测试动态 persona
   curl -X POST http://127.0.0.1:8000/conversations \
     -H "Content-Type: application/json" \
     -d '{"persona_ids": ["custom1", "custom2"], "dynamic_personas": [...]}'
   ```

3. **享受完全动态的 Persona 系统！** 🎉

---

**状态**: ✅ 架构简化完成
**日期**: 2025-02-08
