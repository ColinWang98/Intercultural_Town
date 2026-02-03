extends Control

## 聊天 UI：当前对话对象由 /root/GameState 决定（靠近哪个 NPC 就和谁聊）。
## 需在项目设置 → Autoload 添加 game_state.gd，节点名填 GameState。
## 用 Dialogue Manager 气泡显示 AI 回复时，可开启「仅气泡」以与剧本气泡保持 UI 一致（见 ai_reply_in_balloon_only）。

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

func _get_game_state():
	return get_node_or_null("/root/GameState")

func _ready() -> void:
	if chat_display:
		chat_display.bbcode_enabled = true
		chat_display.scroll_following = true
		chat_display.append_text("[color=gray][系统]: 靠近一位角色即可与其对话。[/color]")
	# TextEdit 时：自动换行、固定高度内可滚动、Enter 发送 / Shift+Enter 换行
	if input_field is TextEdit:
		input_field.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		input_field.set("scroll_fit_content_height", false)  # 不随内容增高，多出部分用滚动
		input_field.set("scroll_fit_content_width", false)   # 不随内容增宽，保持文本框宽度
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

func _process(_delta: float) -> void:
	if current_persona_label != null:
		current_persona_label.text = "当前: " + _get_active_persona_name()

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
	var line = "你 → %s: %s" % [_get_active_persona_name(), text]
	var balloon_shown = _show_player_balloon(line)
	if chat_display and (not ai_reply_in_balloon_only or not balloon_shown):
		chat_display.append_text("\n[color=green][b]你 → %s:[/b][/color] %s" % [_get_active_persona_name(), text])
	input_field.set("text", "")
	input_field.grab_focus()
	_send_to_backend(text)

func _send_to_backend(message: String) -> void:
	if send_button.disabled:
		if chat_display:
			chat_display.append_text("\n[color=gray][系统]: 请等上一条回复后再发。[/color]")
		return
	var url = "http://127.0.0.1:8000/chat"
	var headers = ["Content-Type: application/json"]
	var payload = JSON.stringify({
		"user_input": message,
		"persona": _get_active_persona_id()
	})
	var err = http_request.request(url, headers, HTTPClient.METHOD_POST, payload)
	if err == ERR_BUSY:
		if chat_display:
			chat_display.append_text("\n[color=gray][系统]: 请等上一条回复后再发。[/color]")
		return
	if err != OK:
		if chat_display:
			chat_display.append_text("\n[color=red][系统]: 无法连接到后端服务器[/color]")
		return
	send_button.disabled = true

func _on_http_request_request_completed(_result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	send_button.disabled = false
	if response_code != 200:
		if chat_display:
			chat_display.append_text("\n[color=red][系统]: 服务器返回错误 (HTTP %d)[/color]" % response_code)
		return
	var body_text = body.get_string_from_utf8()
	var response_json = JSON.parse_string(body_text)
	if response_json == null:
		if chat_display:
			chat_display.append_text("\n[color=red][错误]: 收到异常的数据格式[/color]")
		return
	if response_json is Dictionary and response_json.has("reply"):
		var reply: String = response_json["reply"]
		var balloon_shown = _show_reply_balloon(reply)
		# 非「仅气泡」时一律写入 ChatDisplay；仅气泡时若气泡未弹出则回退到 ChatDisplay
		if chat_display and (not ai_reply_in_balloon_only or not balloon_shown):
			chat_display.append_text("\n[color=blue][b]%s:[/b][/color] %s" % [_get_active_persona_name(), reply])
	else:
		if chat_display:
			chat_display.append_text("\n[color=red][错误]: 收到异常的数据格式[/color]")

## 用气泡显示玩家发言（如「你 → 法国人: 哈哈哈」）。返回 true 表示已用气泡显示。
func _show_player_balloon(line: String) -> bool:
	if line.is_empty():
		return false
	var res = player_reply_dialogue
	if res == null:
		var paths = ["res://dialogues/player_reply.dialogue"]
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
	dm.show_dialogue_balloon(res, "", [])
	return true

## 若安装了 Dialogue Manager 且设置了 npc_reply_dialogue，用气泡显示回复。返回 true 表示已用气泡显示，false 表示未显示（可回退到 ChatDisplay）
func _show_reply_balloon(reply: String) -> bool:
	if reply.is_empty():
		return false
	var res = npc_reply_dialogue
	if res == null:
		# 未在检查器里赋值时，尝试常见路径（先检查存在再 load，避免报错）
		var paths = ["res://dialogues/npc_reply.dialogue"]
		for path in paths:
			if ResourceLoader.exists(path):
				res = load(path) as Resource
				break
	if res == null:
		push_warning("chat_interface: Npc Reply Dialogue 未设置且未找到 npc_reply.dialogue，AI 回复将显示在 ChatDisplay。请在聊天 Control 上设置 Npc Reply Dialogue，或将 npc_reply.dialogue 放在 res://dialogues/")
		return false
	var dm = get_node_or_null("/root/DialogueManager")
	if dm == null:
		push_warning("chat_interface: 未找到 DialogueManager，AI 回复将显示在 ChatDisplay。请启用 Dialogue Manager 插件并添加 Autoload")
		return false
	if not dm.has_method("show_dialogue_balloon"):
		return false
	# Dialogue Manager 需通过 Autoload 名引用属性，故先把回复写入 GameState.last_ai_reply，对话里用 {{ GameState.last_ai_reply }}
	var gs = _get_game_state()
	if gs != null:
		gs.set("last_ai_reply", reply)
	dm.show_dialogue_balloon(res, "", [])
	return true
