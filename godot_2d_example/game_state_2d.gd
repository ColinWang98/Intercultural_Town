extends Node
## 全局状态：当前靠近的 NPC 对应的 persona，支持单人/多人对话模式。
## 在项目设置里设为 Autoload，名称填 GameState。

## 单人对话模式：当前靠近的 NPC（若只有一个）
var current_persona_id: String = "french_student_male"
var current_persona_name: String = "法国学生（男）"

## 多人对话模式：当前在范围内的所有 agent（persona_id -> persona_name）
var nearby_agents: Dictionary = {}

## 是否已触发过“群聊开场”（避免进入群聊范围时反复触发）
var group_chat_started: bool = false

## REST：当前会话 id（由 POST /conversations 返回）；同一组 persona 复用同一会话
var current_conversation_id: String = ""
## REST：按“当前 persona 组合”缓存的会话 id（key = _conversation_key()）
var conversation_ids: Dictionary = {}

## 最近一条 AI 回复，供 Dialogue Manager 气泡用 {{ GameState.last_ai_reply }} 显示
var last_ai_reply: String = ""
## 最近一条玩家发言（如「你 → 法国人: 哈哈哈」），供气泡显示
var last_player_message: String = ""

## 添加一个 agent 到范围内
func add_nearby_agent(persona_id: String, persona_name: String) -> void:
	nearby_agents[persona_id] = persona_name
	_update_current_persona()

## 移除一个 agent（离开范围）
func remove_nearby_agent(persona_id: String) -> void:
	nearby_agents.erase(persona_id)
	_update_current_persona()

## 根据 nearby_agents 更新 current_persona（单人时用第一个，多人时用特殊标记）
func _update_current_persona() -> void:
	var count = nearby_agents.size()
	if count == 0:
		current_persona_id = "french_student_male"
		current_persona_name = "法国学生（男）"
		group_chat_started = false
		current_conversation_id = ""
	elif count == 1:
		for pid in nearby_agents:
			current_persona_id = pid
			current_persona_name = nearby_agents[pid]
			break
		group_chat_started = false
		var key = _conversation_key()
		current_conversation_id = conversation_ids.get(key, "")
	else:
		current_persona_id = "group"
		var names: Array[String] = []
		for pid in nearby_agents:
			names.append(nearby_agents[pid])
		current_persona_name = " & ".join(names)
		var key = _conversation_key()
		current_conversation_id = conversation_ids.get(key, "")

## 当前 nearby 对应的会话 key（排序后的 persona_id 拼接，与后端 group_id 一致）
func _conversation_key() -> String:
	var ids: Array[String] = []
	for pid in nearby_agents:
		ids.append(pid)
	ids.sort()
	return "group:" + "+".join(ids)

## REST：保存当前组合的会话 id（创建会话或群聊开场后调用）
func set_conversation_id(conv_id: String) -> void:
	current_conversation_id = conv_id
	conversation_ids[_conversation_key()] = conv_id

## REST：获取当前会话 id（空则需先 POST /conversations）
func get_conversation_id() -> String:
	return current_conversation_id

## 是否处于多人对话模式（两个或更多 agent 在范围内）
func is_group_chat() -> bool:
	return nearby_agents.size() >= 2

## 获取所有在范围内的 persona_id（用于后端请求）
func get_nearby_persona_ids() -> Array[String]:
	var ids: Array[String] = []
	for pid in nearby_agents:
		ids.append(pid)
	return ids

## 是否已触发过法国学生的初始对话（避免重复触发）
var french_students_chat_started: bool = false

func mark_french_students_chat_started() -> void:
	french_students_chat_started = true

func reset_french_students_chat_started() -> void:
	french_students_chat_started = false

## 兼容旧接口（单人模式）
func set_nearby_npc(persona_id: String, persona_name: String) -> void:
	nearby_agents.clear()
	nearby_agents[persona_id] = persona_name
	_update_current_persona()

func clear_nearby_npc() -> void:
	nearby_agents.clear()
	_update_current_persona()
