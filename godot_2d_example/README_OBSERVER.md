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

在聊天 UI 或某个按钮/功能里，发送消息时指定 `persona="observer"`，并把**对话历史**作为 `user_input`：

```gdscript
# 示例：收集最近 N 条对话，发给 observer 总结
var chat_history = "Player: 你好\n法国学生（男）: Bonjour!\n法国学生（女）: Salut!\n..."
var payload = JSON.stringify({
    "user_input": chat_history,
    "persona": "observer"
})
http_request.request("http://127.0.0.1:8000/chat", headers, HTTPClient.METHOD_POST, payload)
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
