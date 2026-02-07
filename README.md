# Backend：多 Persona 聊天 API + Godot 2D Top-down 游戏

FastAPI 后端 + Google ADK，支持多个 AI persona（角色），提供动态 persona 配置和状态机对话管理。

---

## 快速开始

### 1. 配置 Azure OpenAI

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填写你的 API Key
# USE_AZURE=true
# AZURE_OPENAI_API_KEY=your-api-key-here
```

详细配置步骤请参考：**AZURE_SETUP_GUIDE.md**

### 2. 后端启动

```bash
python Main.py
```

**预期输出**：
```
[INFO] 使用 Azure OpenAI 模型
INFO:     Started server process [xxxx]
INFO:     Application startup complete.
```

### 3. 测试 API

```bash
# 运行完整测试
python test_dynamic_persona_complete.py
```

---

## 核心 Persona 列表

**预定义 Persona**（在 `personas.py` 中配置）：
- `mikko`：芬兰学生（男），外向开朗
- `aino`：芬兰学生（女），文静细心
- `religion_expert`：宗教饮食专家
- `allergy_expert`：食物过敏专家
- `observer`：对话观察者，用于总结

**动态 Persona**（API 请求中定义）：
- 可在创建会话时动态添加任意角色
- 支持完整的性格、性别、兴趣等配置
- 无需修改后端代码

---

## API 端点

### RESTful 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/personas` | 获取所有可用 persona 列表 |
| POST | `/conversations` | 创建会话（支持动态 persona） |
| GET | `/conversations` | 获取会话列表（摘要） |
| GET | `/conversations/{id}` | 获取单个会话详情 |
| GET | `/conversations/{id}/messages` | 获取会话消息（支持分页） |
| POST | `/conversations/{id}/messages` | 发送消息 |
| GET | `/conversations/{id}/summary` | 获取 Observer 总结 |

### 创建会话（支持动态 Persona）

```json
POST /conversations
{
  "persona_ids": ["mikko", "sarah"],
  "dynamic_personas": [
    {
      "id": "sarah",
      "name": "Sarah",
      "gender": "Female",
      "personality": "温柔善良的加拿大女生",
      "personality_type": "Ambivert",
      "interests": "徒步、摄影、咖啡",
      "speaking_style": "友善亲切，语气温和",
      "likes": ["徒步", "摄影", "咖啡"],
      "dislikes": ["污染", "粗鲁的行为"],
      "current_state": "刚从徒步旅行回来",
      "location_hint": "咖啡店"
    }
  ]
}
```

### DynamicPersona 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 唯一标识符（匹配 persona_ids） |
| `name` | string | ✅ | 显示名称 |
| `gender` | string | ❌ | 性别：Male/Female/Non-binary/Other |
| `personality` | string | ❌ | 性格描述 |
| `personality_type` | string | ❌ | Extrovert/Introvert/Ambivert |
| `interests` | string | ❌ | 兴趣爱好（逗号分隔） |
| `speaking_style` | string | ❌ | 说话风格描述 |
| `likes` | string[] | ❌ | 喜好列表 |
| `dislikes` | string[] | ❌ | 不喜欢列表 |
| `current_state` | string | ❌ | 当前状态 |
| `location_hint` | string | ❌ | 地点提示 |

---

## 功能特性

### ✅ 核心功能

1. **动态 Persona** - API 请求中定义角色，无需修改后端代码
2. **Gender 参数** - AI 根据性别调整说话语气
3. **状态机架构** - 芬兰学生对话状态管理
   - small_talk：闲聊阶段
   - religion_deep：宗教专家讨论
   - allergy_deep：过敏专家讨论
   - wrap_up：收尾阶段
   - finished：完成总结
4. **重复检测** - 自动检测并拒绝重复的 persona ID
5. **对话过滤** - 移除思考标签（``
 等），限制回复长度（2000 字符）
6. **工具调用日志** - 记录所有 AgentTool 调用
7. **混合模式** - 同时使用预定义和动态 persona

### ✅ 对话功能

- **单人对话**：Player 靠近一个 NPC
- **多人对话**：Player 同时靠近多个 NPC
- **自动开场**：芬兰学生组合自动生成开场对话
- **专家附身**：特定状态下专家以角色身份回应
- **对话总结**：Observer 生成客观总结

---

## 项目结构

```
Backend/
├── Main.py                          # FastAPI 后端入口（1016 行）
├── personas.py                      # Persona 配置与 ADK Agent 构建
├── tools.py                         # AgentTool 注册与缓存
├── test_dynamic_persona_complete.py # 完整测试脚本
├── test_dynamic_persona.py          # 简单测试示例
├── DYNAMIC_PERSONA_EXTENDED_GUIDE.md # Godot 端使用指南
├── FOLDER_STRUCTURE.md              # 文件夹结构说明
├── README_ARCHITECTURE.md           # 项目逻辑架构
└── README_GAME_OVERVIEW.md          # 整体架构说明
```

---

## 状态机架构

芬兰学生对话流程：

```
small_talk (闲聊)
    ↓ 检测关键词
religion_deep / allergy_deep
    ↓ 3-4 轮讨论
small_talk
    ↓ 两个话题都讨论过
wrap_up (收尾)
    ↓ 玩家确认
finished (调用 Observer)
```

---

## 测试

### 运行完整测试

```bash
python test_dynamic_persona_complete.py
```

测试内容：
1. ✅ 两个动态 persona 的对话
2. ✅ 混合预定义和动态 persona
3. ✅ 发送消息验证动态效果

### 手动测试

```bash
# 启动后端
python Main.py

# 创建会话（curl）
curl -X POST http://127.0.0.1:8000/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "persona_ids": ["mikko", "aino"]
  }'

# 发送消息
curl -X POST http://127.0.0.1:8000/conversations/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "你们好！"}'
```

---

## 文档

- `README_ARCHITECTURE.md` - 项目逻辑架构（数据流、编排逻辑、模块职责）
- `README_GAME_OVERVIEW.md` - 整体架构与后端/前端说明
- `DYNAMIC_PERSONA_EXTENDED_GUIDE.md` - Godot 端动态 Persona 配置指南
- `FOLDER_STRUCTURE.md` - 文件夹结构说明

---

## 版本信息

**当前版本**: v2.1
**最后更新**: 2025-02-08
**核心特性**: 动态 Persona、Gender 参数、状态机架构
