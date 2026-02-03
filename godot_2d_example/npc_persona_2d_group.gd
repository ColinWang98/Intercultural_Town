extends Node2D
## 2D 场景中的 NPC（支持多人对话）：挂在 NPC 根节点下，子节点需有 Area2D。
## 玩家进入区域时，通过 GameState.add_nearby_agent 注册；离开时 remove_nearby_agent。
## 当两个或更多 agent 同时在范围内时，GameState 会自动切换到“群聊模式”。
## 当进入“更大范围”（从 1 个变为 2 个或更多）时，会自动触发群聊开场（调用 REST POST /conversations）。
## 对于两个法国学生，后端会自动给出关于 party 准备的开场对话，并返回会话 id 供后续发消息使用。
## 可选：设置 intro_dialogue，靠近时用 Dialogue Manager 播一段剧本招呼。

@export var persona_id: String = "french_student_male"
@export var persona_name: String = "法国学生（男）"
## 可选：靠近时播放的剧本对话资源（.dialogue），如 intro_french.dialogue
@export var intro_dialogue: Resource
## 可选：剧本中的入口标题。若每个 NPC 用单独 .dialogue 文件，通常填 "start"
@export var intro_title: String = "start"
## 为 true 时：离开碰撞范围后自动关闭本 NPC 的招呼气泡
@export var close_balloon_on_exit: bool = true
## 是否为法国学生（仅用于你在 Inspector 里做区分；群聊开场触发已通用化）
@export var is_french_student: bool = false

var _area: Area2D
var _intro_balloon: Node = null

func _ready() -> void:
	_area = _find_area(self)
	if _area:
		if not _area.body_entered.is_connected(_on_body_entered):
			_area.body_entered.connect(_on_body_entered)
		if not _area.body_exited.is_connected(_on_body_exited):
			_area.body_exited.connect(_on_body_exited)
	else:
		push_warning("NpcPersona2DGroup: 未找到 Area2D，无法触发对话切换")

func _find_area(n: Node) -> Area2D:
	if n is Area2D:
		return n
	for c in n.get_children():
		var a = _find_area(c)
		if a:
			return a
	return null

func _on_body_entered(body: Node) -> void:
	if not (body is CharacterBody2D):
		return
	var gs = get_node_or_null("/root/GameState")
	if gs == null:
		push_warning("NpcPersona2DGroup: 未找到 GameState，请在项目设置 → Autoload 添加 game_state_2d.gd，节点名填 GameState")
		return
	gs.add_nearby_agent(persona_id, persona_name)
	
	# 进入更大范围：首次进入群聊时触发开场（只触发一次，避免重复）
	if gs.has_method("is_group_chat") and gs.is_group_chat():
		var already_started = bool(gs.get("group_chat_started")) if gs.has_method("get") else false
		if not already_started:
			gs.set("group_chat_started", true)
			var nearby_ids = gs.get_nearby_persona_ids()
			_try_start_group_chat(nearby_ids)
			return  # 用开场对话代替 intro_balloon
	
	_try_show_intro_balloon()

func _on_body_exited(body: Node) -> void:
	if not (body is CharacterBody2D):
		return
	if close_balloon_on_exit and _intro_balloon != null and is_instance_valid(_intro_balloon):
		_intro_balloon.queue_free()
		_intro_balloon = null
	var gs = get_node_or_null("/root/GameState")
	if gs != null:
		gs.remove_nearby_agent(persona_id)
		# group_chat_started 的重置放在 GameState._update_current_persona() 里统一处理

func _disable_balloon_click() -> void:
	if _intro_balloon == null or not is_instance_valid(_intro_balloon):
		return
	var b: Control = _intro_balloon.get_node_or_null("%Balloon") as Control
	if b == null:
		b = _intro_balloon.get_node_or_null("Balloon") as Control
	if b != null:
		b.mouse_filter = Control.MOUSE_FILTER_IGNORE

func _try_start_group_chat(persona_ids: Array[String]) -> void:
	"""触发群聊的初始对话（REST：POST /conversations，返回会话 id 与开场 messages）。"""
	if persona_ids.is_empty():
		var gs_empty = get_node_or_null("/root/GameState")
		if gs_empty:
			gs_empty.set("group_chat_started", false)
		return
	var req = HTTPRequest.new()
	add_child(req)
	req.request_completed.connect(func(_result: int, res_code: int, _headers: Array, body: PackedByteArray):
		req.queue_free()
		var gs = get_node_or_null("/root/GameState")
		if res_code != 200:
			push_warning("NpcPersona2DGroup: 创建会话失败 HTTP %d" % res_code)
			if gs:
				gs.set("group_chat_started", false)
			return
		var response = JSON.parse_string(body.get_string_from_utf8())
		if not response or not response is Dictionary:
			if gs:
				gs.set("group_chat_started", false)
			return
		if gs and gs.has_method("set_conversation_id") and response.has("id"):
			gs.set_conversation_id(response["id"])
		var reply_text: String = ""
		if response.has("messages") and response["messages"] is Array:
			var parts: Array[String] = []
			for m in response["messages"]:
				if m is Dictionary and m.get("role") == "model" and m.get("content"):
					parts.append(m["content"])
			reply_text = "\n\n".join(parts)
		if reply_text.is_empty() and response.has("reply"):
			reply_text = response["reply"]
		if gs and not reply_text.is_empty():
			gs.set("last_ai_reply", reply_text)
		var dm = get_node_or_null("/root/DialogueManager")
		if dm and dm.has_method("show_dialogue_balloon") and not reply_text.is_empty():
			var reply_dialogue = load("res://dialogues/npc_reply.dialogue") if ResourceLoader.exists("res://dialogues/npc_reply.dialogue") else (load("res://godot_2d_example/dialogues/npc_reply.dialogue") if ResourceLoader.exists("res://godot_2d_example/dialogues/npc_reply.dialogue") else null)
			if reply_dialogue:
				dm.show_dialogue_balloon(reply_dialogue, "")
	)
	var url = "http://127.0.0.1:8000/conversations"
	var headers = ["Content-Type: application/json"]
	var payload = JSON.stringify({"persona_ids": persona_ids})
	var err = req.request(url, headers, HTTPClient.METHOD_POST, payload)
	if err != OK:
		push_warning("NpcPersona2DGroup: 无法触发群聊初始对话")
		var gs_err = get_node_or_null("/root/GameState")
		if gs_err:
			gs_err.set("group_chat_started", false)

func _try_show_intro_balloon() -> void:
	if intro_dialogue == null:
		return
	var dm = get_node_or_null("/root/DialogueManager")
	if dm == null:
		return
	if not dm.has_method("show_dialogue_balloon"):
		return
	_intro_balloon = dm.show_dialogue_balloon(intro_dialogue, "")
	call_deferred("_disable_balloon_click")
