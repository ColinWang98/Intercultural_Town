extends CharacterBody2D
## Top-down（俯视）玩家移动：WASD / 方向键。
## 建议节点结构：
## Player(CharacterBody2D)
## ├─ Sprite2D (可选)
## └─ CollisionShape2D

@export var move_speed: float = 220.0

func _physics_process(_delta: float) -> void:
	var dir := Vector2.ZERO
	# 方向键（ui_*）或 WASD 都可
	if Input.is_action_pressed("ui_up") or Input.is_key_pressed(KEY_W):
		dir.y -= 1
	if Input.is_action_pressed("ui_down") or Input.is_key_pressed(KEY_S):
		dir.y += 1
	if Input.is_action_pressed("ui_left") or Input.is_key_pressed(KEY_A):
		dir.x -= 1
	if Input.is_action_pressed("ui_right") or Input.is_key_pressed(KEY_D):
		dir.x += 1

	velocity = dir.normalized() * move_speed
	move_and_slide()

