extends Control
## NPC 对话选择 UI - 让玩家选择哪些 NPC 参与对话
## 自动显示，玩家可以选择要对话的 NPC

signal chat_partners_selected(persona_ids: Array[String])

var _available_npcs: Array[Dictionary] = []
var _game_state: Node = null
var _checkbox_container: VBoxContainer = null
var _start_button: Button = null

## ============================================================================
## Godot 生命周期
## ============================================================================

func _ready() -> void:
	_setup_ui()
	_center_on_screen()

## ============================================================================
## 设置 UI
## ============================================================================

func _setup_ui() -> void:
	# 设置背景
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP

	var background = ColorRect.new()
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.color = Color(0, 0, 0, 0.8)
	add_child(background)

	# 主容器
	var main_container = VBoxContainer.new()
	main_container.set_anchors_preset(Control.PRESET_CENTER)
	main_container.position = Vector2(0, 0)
	main_container.size = Vector2(400, 500)
	add_child(main_container)

	# 标题
	var title_label = Label.new()
	title_label.text = "选择对话对象"
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_label.add_theme_font_size_override(24)
	main_container.add_child(title_label)

	# NPC 列表容器
	var scroll_container = ScrollContainer.new()
	scroll_container.custom_minimum_size = Vector2(0, 350)
	main_container.add_child(scroll_container)

	_checkbox_container = VBoxContainer.new()
	scroll_container.add_child(_checkbox_container)

	# 按钮容器
	var button_container = HBoxContainer.new()
	button_container.alignment = BoxContainer.ALIGNMENT_CENTER
	main_container.add_child(button_container)

	# 开始对话按钮
	_start_button = Button.new()
	_start_button.text = "开始对话"
	_start_button.custom_minimum_size = Vector2(150, 50)
	_start_button.pressed.connect(_on_start_chat)
	button_container.add_child(_start_button)

	# 取消按钮
	var cancel_button = Button.new()
	cancel_button.text = "取消"
	cancel_button.custom_minimum_size = Vector2(100, 50)
	cancel_button.pressed.connect(_on_cancel)
	button_container.add_child(cancel_button)

func _center_on_screen() -> void:
	position = Vector2(
		(get_viewport_rect().size.x - size.x) / 2,
		(get_viewport_rect().size.y - size.y) / 2
	)

## ============================================================================
## 设置可用的 NPC
## ============================================================================

func set_available_npcs(npcs: Array[Dictionary], game_state: Node) -> void:
	"""设置可选择的 NPC 列表"""
	_available_npcs = npcs
	_game_state = game_state
	_populate_npc_list()

func _populate_npc_list() -> void:
	"""填充 NPC 列表"""
	# 清空现有复选框
	for child in _checkbox_container.get_children():
		child.queue_free()
	await get_tree().process_frame

	for npc in _available_npcs:
		var hbox = HBoxContainer.new()
		_checkbox_container.add_child(hbox)

		# 复选框
		var checkbox = CheckBox.new()
		checkbox.button_pressed = not npc.get("is_self", false)  # 自己默认不选
		checkbox.tooltip_text = "选择 %s 参与对话" % npc["persona_name"]
		hbox.add_child(checkbox)

		# 标签
		var label = Label.new()
		var display_text = npc["persona_name"]
		if npc.get("is_self", false):
			display_text += " (自己)"
		label.text = display_text
		label.custom_minimum_size = Vector2(200, 30)
		hbox.add_child(label)

		# 距离标签（如果有）
		if npc.has("distance"):
			var distance_label = Label.new()
			distance_label.text = str(int(npc["distance"])) + "px"
			distance_label.add_theme_color_override("font_color", Color.GRAY)
			hbox.add_child(distance_label)

## ============================================================================
## 按钮回调
## ============================================================================

func _on_start_chat() -> void:
	"""获取选中的 NPC 并开始对话"""
	var selected_ids = []

	for i in range(_checkbox_container.get_child_count()):
		var hbox = _checkbox_container.get_child(i)
		if hbox.get_child_count() > 0:
			var checkbox = hbox.get_child(0)
			if checkbox.button_pressed:
				var npc = _available_npcs[i]
				selected_ids.append(npc["persona_id"])

	if selected_ids.size() < 2:
		_show_error("至少需要选择 2 个 NPC 才能开始对话")
		return

	# 发送信号
	chat_partners_selected.emit(selected_ids)

	# 关闭 UI
	queue_free()

func _on_cancel() -> void:
	"""取消选择"""
	queue_free()

func _show_error(message: String) -> void:
	"""显示错误消息"""
	var alert = AcceptDialog.new()
	alert.dialog_text = message
	add_child(alert)
	alert.popup_centered()
	alert.confirmed.connect(func(): alert.queue_free())
