extends Node2D
## NPC 对话选择器 - 让 NPC 能够选择其他 NPC 作为聊天对象
## 挂载到 NPC 根节点下，配合 npc_persona_2d_group.gd 使用

## ============================================================================
## 导出变量
## ============================================================================

## 当前 NPC 的 persona ID（必须与 npc_persona_2d_group 中的 persona_id 一致）
@export var persona_id: String = ""

## 当前 NPC 的 persona 名称
@export var persona_name: String = ""

## 是否允许 NPC 自动发起对话（AI 控制）
@export var can_initiate_chat: bool = true

## NPC 检测其他 NPC 的范围（像素）
@export var npc_detection_radius: float = 200.0

## 对话偏好（可选，用于选择聊天对象）
@export_enum("All:所有", "Friends:好友", "Similar:相似性格", "Random:随机")
var chat_preference: String = "All"

## ============================================================================
## 内部变量
## ============================================================================

var _player_in_range: bool = false
var _nearby_npcs: Array[Dictionary] = []
var _detection_area: Area2D = null

## ============================================================================
## Godot 生命周期
## ============================================================================

func _ready() -> void:
	# 创建 NPC 检测区域
	_setup_npc_detection()

	# 等待场景准备完毕
	call_deferred("_find_nearby_npcs")

func _process(_delta: float) -> void:
	# 持续更新附近的 NPC 列表
	if _player_in_range:
		_update_nearby_npcs()

## ============================================================================
## 设置 NPC 检测区域
## ============================================================================

func _setup_npc_detection() -> void:
	# 创建圆形检测区域
	var collision_shape = CollisionShape2D.new()
	var circle_shape = CircleShape2D.new()
	circle_shape.radius = npc_detection_radius
	collision_shape.shape = circle_shape

	# 创建 Area2D
	_detection_area = Area2D.new()
	_detection_area.add_child(collision_shape)
	add_child(__detection_area)

	# 设置碰撞层（检测 NPC，不检测玩家）
	_detection_area.collision_layer = 0
	_detection_area.collision_mask = 4  # 假设 NPC 在第 4 层

	# 连接信号
	_detection_area.body_entered.connect(_on_npc_entered)
	_detection_area.body_exited.connect(_on_npc_exited)

## ============================================================================
## NPC 进入/离开检测范围
## ============================================================================

func _on_npc_entered(body: Node2D) -> void:
	if body == self:
		return

	# 检查是否是 NPC（是否有 persona_id）
	if body.has_method("get") and body.get("persona_id"):
		var npc_info = {
			"node": body,
			"persona_id": body.persona_id,
			"persona_name": body.get("persona_name", ""),
			"distance": global_position.distance_to(body.global_position)
		}
		_nearby_npcs.append(npc_info)
		print(f"[{persona_name}] 检测到附近的 NPC: {npc_info['persona_name']}")

func _on_npc_exited(body: Node2D) -> void:
	for i in range(_nearby_npcs.size() - 1, -1, -1):
		if _nearby_npcs[i]["node"] == body:
			var npc_info = _nearby_npcs[i]
			print(f"[{persona_name}] NPC 离开范围: {npc_info['persona_name']}")
			_nearby_npcs.remove_at(i)
			break

## ============================================================================
## 查找附近的 NPC
## ============================================================================

func _find_nearby_npcs() -> void:
	_nearby_npcs.clear()

	# 在场景中查找所有 NPC
	var npcs = get_tree().get_nodes_in_group("npcs")
	for npc in npcs:
		if npc == self or not npc.has_method("get"):
			continue

		var npc_persona_id = npc.get("persona_id")
		if not npc_persona_id or npc_persona_id == persona_id:
			continue

		var distance = global_position.distance_to(npc.global_position)
		if distance <= npc_detection_radius:
			_nearby_npcs.append({
				"node": npc,
				"persona_id": npc_persona_id,
				"persona_name": npc.get("persona_name", npc_persona_id),
				"distance": distance
			}

	# 按距离排序
	_nearby_npcs.sort_custom(func(a, b): return a["distance"] < b["distance"])

func _update_nearby_npcs() -> void:
	# 实时更新距离
	for npc_info in _nearby_npcs:
		if is_instance_valid(npc_info["node"]):
			npc_info["distance"] = global_position.distance_to(npc_info["node"].global_position)

## ============================================================================
## 玩家进入/离开（用于触发对话）
## ============================================================================

func _on_player_entered() -> void:
	_player_in_range = true
	_find_nearby_npcs()

	# 如果可以发起对话且有附近 NPC，显示选择 UI
	if can_initiate_chat and _nearby_npcs.size() > 0:
		_show_chat_selector()

func _on_player_exited() -> void:
	_player_in_range = false

## ============================================================================
## 显示对话选择 UI
## ============================================================================

func _show_chat_selector() -> void:
	var gs = get_node_or_null("/root/GameState")
	if not gs:
		return

	# 创建选择 UI
	var selector_ui = preload("res://godot_2d_example/chat_selector_ui.tscn").instantiate()
	get_tree().current_scene.add_child(selector_ui)

	# 传递可用的 NPC 列表
	var available_npcs = []
	available_npcs.append({
		"persona_id": persona_id,
		"persona_name": persona_name,
		"is_self": true
	})

	for npc_info in _nearby_npcs:
		available_npcs.append({
			"persona_id": npc_info["persona_id"],
			"persona_name": npc_info["persona_name"],
			"is_self": false
		})

	selector_ui.set_available_npcs(available_npcs, gs)

## ============================================================================
## 获取可选择的聊天对象
## ============================================================================

func get_available_chat_partners() -> Array[Dictionary]:
	"""返回可以聊天的 NPC 列表"""
	var partners = []

	for npc_info in _nearby_npcs:
		partners.append({
			"persona_id": npc_info["persona_id"],
			"persona_name": npc_info["persona_name"],
			"distance": npc_info["distance"]
		})

	return partners

func get_selected_chat_partners() -> Array[String]:
	"""根据偏好返回选中的聊天对象 ID"""
	var partners = get_available_chat_partners()

	if partners.is_empty():
		return []

	match chat_preference:
		"Friends":
			# TODO: 可以从配置中读取好友列表
			return _select_random_partners(partners, 2)
		"Similar":
			# TODO: 可以根据 personality_type 选择
			return _select_random_partners(partners, 2)
		"Random":
			return _select_random_partners(partners, 2)
		_:  # All
			var ids = [persona_id]
			for p in partners:
				ids.append(p["persona_id"])
			return ids

func _select_random_partners(partners: Array[Dictionary], count: int) -> Array[String]:
	var selected = [persona_id]
	var shuffled = partners.duplicate()
	shuffled.shuffle()

	for i in min(count - 1, shuffled.size()):
		selected.append(shuffled[i]["persona_id"])

	return selected

## ============================================================================
## 发起对话
## ============================================================================

func initiate_chat_with(partner_ids: Array[String]) -> void:
	"""发起与指定 NPC 的对话"""
	var gs = get_node_or_null("/root/GameState")
	if not gs:
		return

	# 组合所有参与者的 ID
	var all_ids = [persona_id]
	all_ids.append_array(partner_ids)

	# 触发群聊开场
	if gs.has_method("set_group_chat_started"):
		gs.set("group_chat_started", false)

	if gs.has_method("is_group_chat") and gs.has_method("get_nearby_persona_ids"):
		gs.add_nearby_agent(persona_id, persona_name)
		for pid in partner_ids:
			gs.add_nearby_agent(pid, "")

		if gs.is_group_chat():
			var nearby_ids = gs.get_nearby_persona_ids()

			# 调用群聊
			_try_start_group_chat(nearby_ids)

func _try_start_group_chat(persona_ids: Array[String]) -> void:
	"""触发群聊的初始对话（复制自 npc_persona_2d_group.gd）"""
	if persona_ids.is_empty():
		return

	var req = HTTPRequest.new()
	add_child(req)
	req.request_completed.connect(func(_result: int, res_code: int, _headers: Array, body: PackedByteArray):
		req.queue_free()
		var gs = get_node_or_null("/root/GameState")
		if res_code != 200:
			push_warning("创建会话失败 HTTP %d" % res_code)
			return

		var response = JSON.parse_string(body.get_string_from_utf8())
		if not response or not response is Dictionary:
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

		# 显示对话气泡
		var dm = get_node_or_null("/root/DialogueManager")
		if dm and dm.has_method("show_dialogue_balloon") and not reply_text.is_empty():
			var reply_dialogue = load("res://dialogues/npc_reply.dialogue")
			if reply_dialogue:
				dm.show_dialogue_balloon(reply_dialogue, "")
	)

	var url = "http://127.0.0.1:8000/conversations"
	var headers = ["Content-Type: application/json"]
	var payload = JSON.stringify({"persona_ids": persona_ids})
	var err = req.request(url, headers, HTTPClient.METHOD_POST, payload)
	if err != OK:
		push_warning("无法触发群聊初始对话")
