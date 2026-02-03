extends Node2D
## 2D 场景中的 NPC：挂在 NPC 根节点下，子节点需有 Area2D（用于检测玩家进入）。
## 玩家进入区域时自动切换当前对话对象为该 NPC 的 persona。
## 可选：设置 intro_dialogue + intro_title，靠近时用 Dialogue Manager 播一段剧本招呼。
## 需在项目设置中挂载 GameState（Autoload）；脚本通过 /root/GameState 获取，未添加时不会报错。

@export var persona_id: String = "french_student_male"
@export var persona_name: String = "法国学生（男）"
## 可选：靠近时播放的剧本对话资源（.dialogue），如 intro_french.dialogue
@export var intro_dialogue: Resource
## 可选：剧本中的入口标题。若每个 NPC 用单独 .dialogue 文件，通常填 "start"
@export var intro_title: String = "start"
## 为 true 时：离开碰撞范围后自动关闭本 NPC 的招呼气泡
@export var close_balloon_on_exit: bool = true

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
		push_warning("NpcPersona2D: 未找到 Area2D，无法触发对话切换")

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
		push_warning("NpcPersona2D: 未找到 GameState，请在项目设置 → Autoload 添加 game_state.gd，节点名填 GameState")
		return
	gs.set_nearby_npc(persona_id, persona_name)
	_try_show_intro_balloon()

func _on_body_exited(body: Node) -> void:
	if not (body is CharacterBody2D):
		return
	if close_balloon_on_exit and _intro_balloon != null and is_instance_valid(_intro_balloon):
		_intro_balloon.queue_free()
		_intro_balloon = null
	var gs = get_node_or_null("/root/GameState")
	if gs != null:
		gs.clear_nearby_npc()

func _disable_balloon_click() -> void:
	if _intro_balloon == null or not is_instance_valid(_intro_balloon):
		return
	var b: Control = _intro_balloon.get_node_or_null("%Balloon") as Control
	if b == null:
		b = _intro_balloon.get_node_or_null("Balloon") as Control
	if b != null:
		b.mouse_filter = Control.MOUSE_FILTER_IGNORE

func _try_show_intro_balloon() -> void:
	if intro_dialogue == null:
		return
	var dm = get_node_or_null("/root/DialogueManager")
	if dm == null:
		return
	if not dm.has_method("show_dialogue_balloon"):
		return
	# 传空字符串 "" 让插件用资源的第一个标题/第一行；存气泡引用，离开范围时可自动关（close_balloon_on_exit）
	_intro_balloon = dm.show_dialogue_balloon(intro_dialogue, "")
	# 延后一帧后禁用“点屏幕关”，只保留离开范围自动关
	call_deferred("_disable_balloon_click")

