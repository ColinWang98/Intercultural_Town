# Observer（对话观察者）使用说明

Observer 是一个特殊的 persona，用于**总结玩家和各个 agent 之间的对话**。

---

## 功能

- **不参与对话**：Observer 只做旁观总结，不扮演任何角色
- **客观记录**：按时间顺序记录谁说了什么、关键信息、情绪变化、未解决问题
- **结构化输出**：使用清晰的分段和标题，便于阅读

---

## 使用方法

### 1. 在 Godot 中调用

使用 REST：先创建仅含 observer 的会话，再发一条消息（内容为对话历史或「请总结上述对话」）：

```gdscript
# 示例：先 POST /conversations 创建 observer 会话，再 POST .../messages 发总结请求
# 1) 创建会话
var payload_create = JSON.stringify({"persona_ids": ["observer"]})
http_request.request("http://127.0.0.1:8000/conversations", headers, HTTPClient.METHOD_POST, payload_create)
# 2) 收到响应后取 id，再发消息（content 为对话历史或「请总结上述对话：\n」+ 历史）
var chat_history = "Player: 你好\n法国学生（男）: Bonjour!\n法国学生（女）: Salut!\n..."
var payload_msg = JSON.stringify({"content": "请总结上述对话：\n" + chat_history})
http_request.request("http://127.0.0.1:8000/conversations/" + conversation_id + "/messages", headers, HTTPClient.METHOD_POST, payload_msg)
# 响应中的 reply 即为 Observer 的总结
```

### 2. 后端处理

Observer 使用 `qwen3:4b-instruct` 模型，会按照 instruction 中的规则进行总结。

---

## 输出格式示例

Observer 的回复通常包含：

- **对话概览**：简要说明发生了什么
- **关键信息**：重要事实、决定、计划
- **情绪与关系**：各方情绪状态和关系动态
- **未解决问题**：待完成的话题或疑问

---

## 注意事项

- Observer **不会主动参与对话**，需要手动调用
- 适合在对话告一段落时调用，帮助玩家回顾和理解
- 可以定期调用（如每 10 轮对话后），或由玩家主动触发（如点击「总结对话」按钮）
