extends Node2D
## 2D 场景中的 NPC（支持玩家选择聊天对象）
## 挂在 NPC 根节点下，子节点需有 Area2D
## 当玩家靠近时，可以选择让哪些 NPC 开始对话

## ============================================================================
## 导出变量
## ============================================================================

@export var persona_id: String = "mikko"
@export var persona_name: String = "Mikko"

## 对话模式
@export_enum("Auto:自动检测", "Manual:手动选择", "None:禁用")
var chat_mode: String = "Auto"

## 是否显示对话提示图标
@export var show_chat_indicator: bool = true

## ============================================================================
## 内部变量
## ============================================================================

var _area: Area2D = null
var _chat_ui_shown: bool = false
var _nearby_npcs: Array = []

## ============================================================================
## Godot 生命周期
## ============================================================================

func _ready() -> void:
	_area = _find_area(self)
	if _area:
		if not _area.body_entered.is_connected(_on_body_entered):
			_area.body_entered.connect(_on_body_entered)
		if not _area.body_exited.is_connected(_on_body_exited):
			_area.body_exited.connect(_on_body_exited)
	else:
		push_warning("NpcPersonaInteractive: 未找到 Area2D")

	# 添加到 NPC 组，方便其他 NPC 查找
	add_to_group("npcs")

	# 创建对话提示图标
	if show_chat_indicator:
		_create_chat_indicator()

func _find_area(n: Node) -> Area2D:
	if n is Area2D:
		return n
	for c in n.get_children():
		var a = _find_area(c)
		if a:
			return a
	return null

## ============================================================================
## 玩家进入/离开检测范围
## ============================================================================

func _on_body_entered(body: Node) -> void:
	if not (body is CharacterBody2D):
		return

	var gs = get_node_or_null("/root/GameState")
	if not gs:
		push_warning("未找到 GameState")
		return

	# 注册到 GameState
	if gs.has_method("add_nearby_agent"):
		gs.add_nearby_agent(persona_id, persona_name)

	# 检查是否需要显示对话选择 UI
	match chat_mode:
		"Auto":
			# 自动检测并提示
			_nearby_npcs = _find_nearby_npcs()
			if _nearby_npcs.size() >= 1:  # 有其他 NPC 在附近
				_show_chat_prompt()
		"Manual":
			# 显示手动选择按钮
			_show_manual_chat_button()
		"None":
			pass  # 禁用

func _on_body_exited(body: Node) -> void:
	if not (body is CharacterBody2D):
		return

	# 隐藏对话提示
	_hide_chat_prompt()

	# 从 GameState 移除
	var gs = get_node_or_null("/root/GameState")
	if gs and gs.has_method("remove_nearby_agent"):
		gs.remove_nearby_agent(persona_id)

## ============================================================================
## 查找附近的 NPC
## ============================================================================

func _find_nearby_npcs() -> Array:
	"""查找附近的 NPC"""
	var nearby = []
	var npcs = get_tree().get_nodes_in_group("npcs")

	for npc in npcs:
		if npc == self:
			continue

		var distance = global_position.distance_to(npc.global_position)
		if distance <= 150.0:  # NPC 检测范围
			nearby.append({
				"node": npc,
				"persona_id": npc.persona_id,
				"persona_name": npc.persona_name,
				"distance": distance
			})

	return nearby

## ============================================================================
## 显示对话提示
## ============================================================================

var _chat_prompt_label: Label = null

func _show_chat_prompt() -> void:
	if _chat_prompt_label:
		return

	_chat_prompt_label = Label.new()
	_chat_prompt_label.text = "按 E 选择对话对象"
	_chat_prompt_label.position = Vector2(-50, -80)
	_chat_prompt_label.add_theme_font_size_override(16)
	_chat_prompt_label.add_theme_color_override("font_color", Color.YELLOW)
	_chat_prompt_label.z_index = 10
	add_child(_chat_prompt_label)

func _hide_chat_prompt() -> void:
	if _chat_prompt_label:
		_chat_prompt_label.queue_free()
		_chat_prompt_label = null

## ============================================================================
## 手动对话按钮
## ============================================================================

var _chat_button: Button = null

func _show_manual_chat_button() -> void:
	if _chat_button:
		return

	_chat_button = Button.new()
	_chat_button.text = "选择对话"
	_chat_button.position = Vector2(-40, -60)
	_chat_button.custom_minimum_size = Vector2(80, 30)
	_chat_button.pressed.connect(_on_chat_button_pressed)
	_chat_button.z_index = 10
	add_child(_chat_button)

func _on_chat_button_pressed() -> void:
	_open_chat_selector()

## ============================================================================
## 对话选择器
## ============================================================================

func _open_chat_selector() -> void:
	"""打开对话选择 UI"""
	var gs = get_node_or_null("/root/GameState")
	if not gs:
		return

	# 收集所有附近的 NPC
	var all_nearby = [self]
	all_nearby.append_array(_find_nearby_npcs())

	# 创建选择 UI
	var selector_ui = _create_chat_selector_ui()
	get_tree().current_scene.add_child(selector_ui)

	# 设置可用 NPC
	var available_npcs = []
	for npc in all_nearby:
		available_npcs.append({
			"persona_id": npc.persona_id,
			"persona_name": npc.persona_name,
			"distance": 0.0  # 简化
		})

	selector_ui.set_available_npcs(available_npcs, gs)
	selector_ui.chat_partners_selected.connect(_on_chat_partners_selected)

func _create_chat_selector_ui() -> Control:
	"""创建对话选择 UI"""
	var selector = preload("res://godot_2d_example/chat_selector_ui.tscn")
	if ResourceLoader.exists(selector):
		return selector.instantiate()
	else:
		# 如果资源不存在，直接创建
		var ui = Control.new()
		ui.set_script(load("res://godot_2d_example/chat_selector_ui.gd"))
		return ui

func _on_chat_partners_selected(persona_ids: Array[String]) -> void:
	"""开始对话"""
	var gs = get_node_or_null("/root/GameState")
	if not gs:
		return

	# 确保所有 NPC 都在 GameState 中注册
	for pid in persona_ids:
		gs.add_nearby_agent(pid, "")

	# 触发群聊开场
	if gs.has_method("set"):
		gs.set("group_chat_started", false)

	# 发起对话
	_start_group_chat(persona_ids)

func _start_group_chat(persona_ids: Array[String]) -> void:
	"""开始群聊"""
	var req = HTTPRequest.new()
	add_child(req)
	req.request_completed.connect(func(_result, res_code, _headers, body):
		req.queue_free()
		if res_code != 200:
			push_warning("创建会话失败 HTTP %d" % res_code)
			return

		var response = JSON.parse_string(body.get_string_from_utf8())
		if not response or not response is Dictionary:
			return

		var gs = get_node_or_null("/root/GameState")
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

		# 显示对话
		_show_dialogue_balloon(reply_text)
	)

	var url = "http://127.0.0.1:8000/conversations"
	var headers = ["Content-Type: application/json"]
	var payload = JSON.stringify({"persona_ids": persona_ids})
	var err = req.request(url, headers, HTTPClient.METHOD_POST, payload)
	if err != OK:
		push_warning("无法触发群聊初始对话")

func _show_dialogue_balloon(text: String) -> void:
	"""显示对话气泡"""
	var dm = get_node_or_null("/root/DialogueManager")
	if dm and dm.has_method("show_dialogue_balloon"):
		var reply_dialogue = load("res://dialogues/npc_reply.dialogue")
		if reply_dialogue and ResourceLoader.exists(reply_dialogue.resource_path):
			dm.show_dialogue_balloon(reply_dialogue, "")

## ============================================================================
## 输入处理（按 E 键）
## ============================================================================

func _input(event: InputEvent) -> void:
	if not _chat_prompt_label:
		return

	if event.is_action_pressed("ui_accept") and _nearby_npcs.size() > 0:
		_open_chat_selector()
		get_viewport().set_input_as_handled()

## ============================================================================
## 对话指示器
## ============================================================================

func _create_chat_indicator() -> void:
	var indicator = ColorRect.new()
	indicator.size = Vector2(20, 20)
	indicator.position = Vector2(-10, -60)
	indicator.color = Color(1, 1, 0, 0.7)  # 黄色
	indicator.z_index = 5

	# 添加简单的动画
	var tween = create_tween()
	tween.set_loops()
	tween.tween_property(indicator, "modulate:a", 0.3, 0.5)
	tween.tween_property(indicator, "modulate:a", 1.0, 0.5)

	add_child(indicator)
