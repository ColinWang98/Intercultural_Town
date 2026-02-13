# Analyser Integration Complete

## Date: 2025-02-13

## Summary

✅ **Analyser 集成完成并验证通过**

## 修改内容

### 1. 移除重复函数定义
- **问题**: Main.py 中存在两个 `_call_analyser()` 函数定义
  - 第一个: lines 860-979 (旧版)
  - 第二个: lines 1428-1552 (新版)
- **修复**: 移除了第一个重复定义，保留功能更完整的第二个版本

### 2. 修复语法错误
- **问题 1**: 缺少闭合括号
  ```python
  # 修复前
  user_msg = types.Content(role="user", parts=[types.Part(text="\n".join(prompt_parts)]

  # 修复后
  user_msg = types.Content(role="user", parts=[types.Part(text="\n".join(prompt_parts))])
  ```

- **问题 2**: 缩进错误 (lines 1412-1413)
  ```python
  # 修复前 - 错误缩进
  if clean_reply.startswith("```json"):
      clean_reply = clean_reply[7:]
      if clean_reply.startswith("```"):
          clean_reply = clean_reply[3:]
  # 移除后3个字符（包括可能的结束标记）
      clean_reply = clean_reply[:-3]  # 错误：缩进导致在不该执行时执行

  # 修复后 - 正确缩进
  if clean_reply.startswith("```json"):
      clean_reply = clean_reply[7:]
  if clean_reply.startswith("```"):
      clean_reply = clean_reply[3:]
  # 移除后3个字符（包括可能的结束标记）
  if clean_reply.endswith("```"):
      clean_reply = clean_reply[:-3]
  ```

### 3. 保留的核心功能

`_call_analyser()` 函数现在包含以下功能：

#### 输入参数
- `conversation_id: str` - 会话 ID
- `messages: List[dict]` - 消息历史
- `event_context: Optional[dict]` - 事件上下文（title, description, topics）
- `round_number: int = 0` - 轮次（用于第5轮 emoji 功能）

#### 评估提示构建
1. 对话历史格式化
2. 事件上下文信息
3. 三个评估标准：
   - 对话充分性（核心主题、有效互动、对话轮次≥3）
   - 主题相关性（内容相关、无偏离）
   - 个人喜好保持（agents 表达 dislikes）

4. JSON 输出格式规范
5. 第5轮特殊任务 - Emoji 建议：
   - mood: 对话氛围
   - emojis: 推荐的 emoji 列表
   - target_agents: 目标 agents
   - reason: 推荐理由

#### 返回值
```python
{
    "passed": bool,           # 是否通过评估
    "overall_score": int,     # 总体评分 0-100
    "criteria": {
        "topic_relevance": {...},
        "discussion_depth": {...},
        "dislikes_maintained": {...}
    },
    "issues": [],             # 发现的问题列表
    "suggestions": [],         # 改进建议列表
    "needs_intervention": bool, # 是否需要干预
    "emoji_suggestion": {...}  # 第5轮时的 emoji 建议
}
```

### 4. 集成点验证

Analyser 在 `_run_chat_round()` 中的3个集成点：

1. **第5轮 Emoji 建议** (line ~410)
   ```python
   if user_message_count == 5:
       evaluation = await _call_analyser(conversation_id, messages, event_context, round_number=5)
       if evaluation.get("emoji_suggestion"):
           # 处理 emoji 建议并让 agents 发送
   ```

2. **每3轮干预检查** (line ~461)
   ```python
   elif user_message_count >= 3 and user_message_count % 3 == 0:
       evaluation = await _call_analyser(conversation_id, messages, event_context)
       if evaluation.get("needs_intervention"):
           # 生成引导性提示并让目标 agents 回应
   ```

3. **评估阶段** (line ~488)
   ```python
   elif phase == "evaluation":
       evaluation = await _call_analyser(conversation_id, messages, event_context)
       # 生成评估报告并切换到 finished 状态
   ```

## 验证结果

### 语法检查
```bash
python -X utf8 -c "import Main; print('Main.py syntax OK')"
# 输出: Main.py syntax OK
```

### Persona 可用性
```bash
python -X utf8 -c "import personas; print(list(personas.PERSONAS.keys()))"
# 输出: ['mikko', 'aino', 'observer', 'analyser']
```

### 函数签名
```python
_call_analyser(
    conversation_id: str,
    messages: List[dict],
    event_context: Optional[dict] = None,
    round_number: int = 0
) -> dict
```

### 集成验证
- `_call_analyser` 在 `_run_chat_round` 中被引用 **3 次**
- 包含 emoji 逻辑 ✓
- 包含干预逻辑 ✓

## 使用流程

### 1. 用户发送消息
```
POST /conversations/{id}/messages
{
  "content": "你们想吃什么？",
  "player_name": "Player"
}
```

### 2. 后端处理流程
```
_run_chat_round()
  └─> small_talk phase
       ├─> _finnish_students_respond() - agents 回应
       ├─> (第5轮) _call_analyser(round_number=5) - emoji 建议
       │    └─> agents 发送 emoji 消息
       ├─> (每3轮) _call_analyser() - 检查是否需要干预
       │    └─> 如果 needs_intervention，生成引导性提示
       └─> (用户说"结束") 切换到 evaluation phase

  └─> evaluation phase
       ├─> _call_analyser() - 完整评估
       ├─> 生成评估报告
       ├─> _call_observer() - 观察者总结
       └─> _finnish_students_respond() - 最后回应
       └─> 切换到 finished 状态

  └─> finished phase
       └─> _call_observer() - 仅观察者总结
```

### 3. Analyser 输出示例

#### 普通评估
```json
{
  "passed": false,
  "overall_score": 45,
  "criteria": {
    "topic_relevance": {"passed": true, "score": 80, "reason": "讨论了食物主题"},
    "discussion_depth": {"passed": false, "score": 30, "reason": "对话轮次不足"},
    "dislikes_maintained": {"passed": false, "score": 25, "reason": "agents 未表达 dislikes"}
  },
  "issues": [
    "对话轮次只有2轮，低于要求的3轮",
    "没有 agents 表达他们的饮食禁忌或偏好"
  ],
  "suggestions": [
    "继续对话，让每个 agent 至少发言一次",
    "引导 agents 谈论他们不喜欢或不能吃的食物"
  ],
  "needs_intervention": true,
  "intervention": {
    "target_agents": ["mikko"],
    "prompt": "Mikko，请聊聊你不喜欢吃的食物"
  }
}
```

#### 第5轮 Emoji 建议
```json
{
  "passed": true,
  "overall_score": 85,
  "criteria": {...},
  "emoji_suggestion": {
    "mood": "happy",
    "emojis": ["😊", "🎉"],
    "target_agents": ["mikko", "aino"],
    "reason": "对话氛围愉快，参与者对聚餐计划感到兴奋"
  }
}
```

## 下一步工作

1. ✅ 后端 Analyser 集成完成
2. ⏳ 前端 Godot 集成
   - 在 UI 中显示 emoji 建议
   - 显示评估报告
   - 处理干预消息
3. ⏳ 端到端测试
   - 完整对话流程测试
   - emoji 功能测试
   - 干预机制测试
4. ⏳ 性能优化
   - 减少不必要的 analyser 调用
   - 缓存评估结果

## 相关文件

- **personas.py**: Analyser persona 定义和配置
- **Main.py**: 对话流程和 analyser 集成
- **tools.py**: AgentTool 注册系统

## 注意事项

1. **Windows 编码问题**: 运行时使用 `python -X utf8` 以避免中文显示乱码
2. **模型依赖**: Analyser 需要 GPT-4o 或同等能力的模型才能准确评估
3. **JSON 解析**: 已处理模型返回的 markdown 包装，自动移除 ` ```json ` 和 ` ``` ` 标记
4. **错误处理**: 当 JSON 解析失败时返回默认错误响应，不会导致程序崩溃
