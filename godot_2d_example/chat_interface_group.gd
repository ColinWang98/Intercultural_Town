extends Control
## 2D Top-down 场景聊天 UI：支持单人/多人对话模式。
## 当前对话对象由 /root/GameState 决定（靠近哪个 NPC 就和谁聊；两个或更多 NPC 在范围内时自动切换为群聊）。
## 需在项目设置 → Autoload 添加 game_state_2d.gd，节点名填 GameState。
## 用 Dialogue Manager 气泡显示 AI 回复时，可开启「仅气泡」以与剧本气泡保持 UI 一致（见 ai_reply_in_balloon_only）。
## 若出现 "Assertion failed: response not found"，请在项目设置中确认「Balloon Path」指向的气泡场景包含
## Dialogue Manager 要求的节点（如 Balloon、DialogueLabel、ResponsesMenu 及 response_template），或使用插件自带的 example_balloon。

@onready var http_request: HTTPRequest = $HTTPRequest
@onready var input_field: Control = $InputBar  # LineEdit 或 TextEdit，脚本里用 .text 和 grab_focus()
@onready var chat_display: RichTextLabel = get_node_or_null("ChatDisplay") as RichTextLabel
@onready var send_button: Button = $SendButton
@onready var current_persona_label: Label = get_node_or_null("CurrentPersonaLabel") as Label

## Dialogue Manager 对话资源，用于把后端回复以气泡显示。.dialogue 里需有节点，内容为 {{ GameState.last_ai_reply }}
@export var npc_reply_dialogue: Resource
## 玩家发言气泡用对话资源，内容为 {{ GameState.last_player_message }}（如「你 → 法国人: 哈哈哈」）
@export var player_reply_dialogue: Resource
## 为 true 时：玩家发言与 AI 回复都尽量用气泡显示，不写入 ChatDisplay；为 false 时同时写入 ChatDisplay。需设置对应 dialogue 和 Balloon Path。
@export var ai_reply_in_balloon_only: bool = true

## REST：创建会话后待发送的消息（先 POST /conversations 再 POST .../messages）
var _pending_message: String = ""
var _creating_conversation: bool = false

func _get_game_state():
	return get_node_or_null("/root/GameState")

## 根据 HTTPRequest.request() 的返回值给出用户可读的提示（用于 err != OK 时）
func _request_error_message(err: int) -> String:
	if err == Error.ERR_CANT_CONNECT or err == Error.ERR_CONNECTION_ERROR:
		return "无法连接：请确认后端已启动 (127.0.0.1:8000)"
	if err == Error.ERR_CANT_RESOLVE:
		return "无法解析服务器地址"
	return "请求失败 (错误码 %d)" % err

func _ready() -> void:
	if chat_display:
		chat_display.bbcode_enabled = true
		chat_display.scroll_following = true
		chat_display.append_text("[color=gray][系统]: 靠近一位角色即可与其对话；同时靠近两位或更多角色可进行群聊。[/color]")
	# TextEdit 时：自动换行、固定高度内可滚动、Enter 发送 / Shift+Enter 换行（1 = LINE_WRAPPING_BOUNDARY）
	if input_field is TextEdit:
		input_field.set("wrap_mode", 1)
		input_field.set("scroll_fit_content_height", false)
		input_field.set("scroll_fit_content_width", false)
		if not input_field.gui_input.is_connected(_on_input_bar_gui_input):
			input_field.gui_input.connect(_on_input_bar_gui_input)

func _get_active_persona_id() -> String:
	var gs = _get_game_state()
	if gs == null:
		return "french_student_male"
	var v = gs.get("current_persona_id")
	return v if v else "french_student_male"

func _get_active_persona_name() -> String:
	var gs = _get_game_state()
	if gs == null:
		return "法国学生（男）"
	var v = gs.get("current_persona_name")
	return v if v else "法国学生（男）"

func _get_nearby_persona_ids() -> Array[String]:
	var gs = _get_game_state()
	if gs == null:
		return ["french_student_male"]
	if gs.has_method("get_nearby_persona_ids"):
		return gs.get_nearby_persona_ids()
	return [gs.get("current_persona_id")]

func _process(_delta: float) -> void:
	if current_persona_label != null:
		var gs = _get_game_state()
		var label_text := "当前: "
		if gs != null and gs.has_method("is_group_chat") and gs.is_group_chat():
			label_text += "[群聊] " + _get_active_persona_name()
		else:
			label_text += _get_active_persona_name()
		current_persona_label.text = label_text

func _on_input_bar_gui_input(event: InputEvent) -> void:
	if input_field is TextEdit and event is InputEventKey:
		var k := event as InputEventKey
		if k.pressed and not k.echo and (k.keycode == KEY_ENTER or k.keycode == KEY_KP_ENTER):
			if not k.shift_pressed:
				get_viewport().set_input_as_handled()
				_on_send_button_pressed()
				return

func _on_send_button_pressed() -> void:
	var text: String = (input_field.get("text") as String).strip_edges()
	if text == "":
		return
	var gs = _get_game_state()
	var is_group = gs != null and gs.has_method("is_group_chat") and gs.is_group_chat()
	var line: String
	if is_group:
		line = "你 → [群聊]: %s" % text
	else:
		line = "你 → %s: %s" % [_get_active_persona_name(), text]
	var balloon_shown = _show_player_balloon(line)
	if chat_display and (not ai_reply_in_balloon_only or not balloon_shown):
		if is_group:
			chat_display.append_text("\n[color=green][b]你 → [群聊]:[/b][/color] %s" % text)
		else:
			chat_display.append_text("\n[color=green][b]你 → %s:[/b][/color] %s" % [_get_active_persona_name(), text])
	input_field.set("text", "")
	input_field.grab_focus()
	_send_to_backend(text)

func _send_to_backend(message: String) -> void:
	if send_button.disabled:
		if chat_display:
			chat_display.append_text("\n[color=gray][系统]: 请等上一条回复后再发。[/color]")
		return
	var gs = _get_game_state()
	var conv_id: String = ""
	if gs != null and gs.has_method("get_conversation_id"):
		conv_id = gs.get_conversation_id()
	var headers = ["Content-Type: application/json"]
	var url: String
	var payload: String
	var err: int
	if conv_id.is_empty():
		# 先创建会话，再发消息（完成回调里会发 _pending_message）
		_pending_message = message
		_creating_conversation = true
		var persona_ids = _get_nearby_persona_ids()
		if persona_ids.is_empty():
			persona_ids.append(_get_active_persona_id())
		url = "http://127.0.0.1:8000/conversations"
		payload = JSON.stringify({"persona_ids": persona_ids})
		err = http_request.request(url, headers, HTTPClient.METHOD_POST, payload)
		if err == ERR_BUSY:
			if chat_display:
				chat_display.append_text("\n[color=gray][系统]: 请等上一条回复后再发。[/color]")
			_creating_conversation = false
			_pending_message = ""
			return
		if err != OK:
			if chat_display:
				chat_display.append_text("\n[color=red][系统]: %s[/color]" % _request_error_message(err))
			_creating_conversation = false
			_pending_message = ""
			return
		send_button.disabled = true
		return
	url = "http://127.0.0.1:8000/conversations/%s/messages" % conv_id
	payload = JSON.stringify({"content": message})
	err = http_request.request(url, headers, HTTPClient.METHOD_POST, payload)
	if err == ERR_BUSY:
		if chat_display:
			chat_display.append_text("\n[color=gray][系统]: 请等上一条回复后再发。[/color]")
		return
	if err != OK:
		if chat_display:
			chat_display.append_text("\n[color=red][系统]: %s[/color]" % _request_error_message(err))
		return
	send_button.disabled = true

func _on_http_request_request_completed(_result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	send_button.disabled = false
	if response_code != 200:
		if chat_display:
			chat_display.append_text("\n[color=red][系统]: 服务器返回错误 (HTTP %d)[/color]" % response_code)
		if _creating_conversation:
			_creating_conversation = false
			_pending_message = ""
		return
	var body_text = body.get_string_from_utf8()
	var response_json = JSON.parse_string(body_text)
	if response_json == null:
		if chat_display:
			chat_display.append_text("\n[color=red][错误]: 收到异常的数据格式[/color]")
		if _creating_conversation:
			_creating_conversation = false
			_pending_message = ""
		return
	# REST：刚创建会话，接着发待发送消息
	if _creating_conversation and response_json is Dictionary and response_json.has("id"):
		var gs = _get_game_state()
		if gs != null and gs.has_method("set_conversation_id"):
			gs.set_conversation_id(response_json["id"])
		_creating_conversation = false
		var msg = _pending_message
		_pending_message = ""
		if msg.is_empty():
			return
		var conv_id: String = gs.get_conversation_id() if gs else ""
		if conv_id.is_empty():
			return
		var url = "http://127.0.0.1:8000/conversations/%s/messages" % conv_id
		var headers = ["Content-Type: application/json"]
		var payload = JSON.stringify({"content": msg})
		var err = http_request.request(url, headers, HTTPClient.METHOD_POST, payload)
		if err == ERR_BUSY:
			if chat_display:
				chat_display.append_text("\n[color=gray][系统]: 请等上一条回复后再发。[/color]")
			return
		if err != OK:
			if chat_display:
				chat_display.append_text("\n[color=red][系统]: %s[/color]" % _request_error_message(err))
			return
		send_button.disabled = true
		return
	# 正常消息回复：reply 在 POST /conversations/{id}/messages 的返回里
	if response_json is Dictionary and response_json.has("reply"):
		var reply: String = response_json["reply"]
		var balloon_shown = _show_reply_balloon(reply)
		if chat_display and (not ai_reply_in_balloon_only or not balloon_shown):
			chat_display.append_text("\n[color=blue][b]回复:[/b][/color] %s" % reply)
	else:
		if chat_display:
			chat_display.append_text("\n[color=red][错误]: 收到异常的数据格式[/color]")

func _show_player_balloon(line: String) -> bool:
	if line.is_empty():
		return false
	var res = player_reply_dialogue
	if res == null:
		var paths = ["res://dialogues/player_reply.dialogue", "res://godot_2d_example/dialogues/player_reply.dialogue"]
		for path in paths:
			if ResourceLoader.exists(path):
				res = load(path) as Resource
				break
	if res == null:
		return false
	var dm = get_node_or_null("/root/DialogueManager")
	if dm == null or not dm.has_method("show_dialogue_balloon"):
		return false
	var gs = _get_game_state()
	if gs != null:
		gs.set("last_player_message", line)
	var extra_states: Array = [gs] if gs != null else []
	dm.show_dialogue_balloon(res, "", extra_states)
	return true

func _show_reply_balloon(reply: String) -> bool:
	if reply.is_empty():
		return false
	var res = npc_reply_dialogue
	if res == null:
		var paths = ["res://dialogues/npc_reply.dialogue", "res://godot_2d_example/dialogues/npc_reply.dialogue"]
		for path in paths:
			if ResourceLoader.exists(path):
				res = load(path) as Resource
				break
	if res == null:
		push_warning("chat_interface_group: Npc Reply Dialogue 未设置且未找到 npc_reply.dialogue，AI 回复将显示在 ChatDisplay。")
		return false
	var dm = get_node_or_null("/root/DialogueManager")
	if dm == null:
		push_warning("chat_interface_group: 未找到 DialogueManager，AI 回复将显示在 ChatDisplay。")
		return false
	if not dm.has_method("show_dialogue_balloon"):
		return false
	var gs = _get_game_state()
	if gs != null:
		gs.set("last_ai_reply", reply)
	var extra_states: Array = [gs] if gs != null else []
	dm.show_dialogue_balloon(res, "", extra_states)
	return true
