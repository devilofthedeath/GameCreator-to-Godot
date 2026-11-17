import os

from converter.config import GODOT_DIR

SCRIPTS = {
    "anim_sprite.gd": """extends Sprite2D
@export var fps: float = 10.0

var timer: float = 0.0


func _process(delta):
	if hframes <= 1:
		return
	timer += delta
	if timer >= 1.0 / max(1.0, fps):
		timer = 0.0
		frame = (frame + 1) % hframes
""",

    "bullet.gd": """extends Area2D

var direction: int = 1
var speed: float = 550.0
var damage: int = 15


func _ready():
	body_entered.connect(_on_body)
	area_entered.connect(_on_area)
	await get_tree().create_timer(2.0).timeout
	queue_free()


func _process(delta):
	position.x += direction * speed * delta


func _on_body(body):
	if body.is_in_group("player"):
		return
	if body.has_method("take_damage"):
		body.take_damage(damage)
	queue_free()


func _on_area(area):
	if area.has_method("on_bullet_hit"):
		area.on_bullet_hit()
		queue_free()
	elif area.has_method("take_damage"):
		area.take_damage(damage)
		queue_free()
""",

    "enemy.gd": """extends CharacterBody2D

@export var speed: float = 90.0
@export var hp: int = 30
@export var start_visible: bool = true
@export var start_active: bool = true
@export var listener_num: int = 0
@export var vis_on_switch: int = 0
@export var act_on_switch: int = 0
@export var rem_on_switch: int = 0

var dir: int = -1
var is_active: bool = true
var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")


func _ready():
	visible = start_visible
	is_active = start_active
	if listener_num > 0:
		add_to_group("switch_listeners")


func on_switch_event(num: int, state: bool):
	if num != listener_num:
		return
	if rem_on_switch == 1 and state:
		queue_free()
		return
	if vis_on_switch == 1:
		visible = state
	if act_on_switch == 1:
		is_active = state


func _physics_process(delta):
	if not is_active:
		return
	if not is_on_floor():
		velocity.y += gravity * delta
	velocity.x = dir * speed
	move_and_slide()
	if is_on_wall():
		dir *= -1
		if has_node("Sprite2D"):
			$Sprite2D.flip_h = dir > 0


func take_damage(amount: int):
	hp -= amount
	if hp <= 0:
		queue_free()
""",

    "solid_block.gd": """extends StaticBody2D

@export var start_visible: bool = true
@export var start_active: bool = true
@export var listener_num: int = 0
@export var vis_on_switch: int = 0
@export var act_on_switch: int = 0
@export var rem_on_switch: int = 0


func _ready():
	visible = start_visible
	if has_node("CollisionShape2D"):
		$CollisionShape2D.set_deferred("disabled", not start_active)
	if listener_num > 0:
		add_to_group("switch_listeners")


func on_switch_event(num: int, state: bool):
	if num != listener_num:
		return
	if rem_on_switch == 1 and state:
		queue_free()
		return
	if vis_on_switch == 1:
		visible = state
	if act_on_switch == 1 and has_node("CollisionShape2D"):
		$CollisionShape2D.set_deferred("disabled", not state)
""",

    "interactive.gd": """extends Area2D

@export var role: String = "DESIGN"
@export var start_visible: bool = true
@export var start_active: bool = true
@export var listener_num: int = 0
@export var vis_on_switch: int = 0
@export var act_on_switch: int = 0
@export var rem_on_switch: int = 0
@export var switch_num: int = 0
@export var switch_mode: int = 2
@export var by_bullet: bool = false
@export var by_melee: bool = false
@export var ignore_player: bool = false
@export var action_score: int = 0
@export var popup_index: int = 0
@export var grant_gun: bool = false
@export var timer_id: int = 0
@export var timer_secs: float = 0.0

var is_active: bool = true


func _ready():
	visible = start_visible
	is_active = start_active
	set_deferred("monitoring", start_active)
	if listener_num > 0 or role == "DOOR":
		add_to_group("switch_listeners")
	body_entered.connect(_on_body)


func on_switch_event(num: int, state: bool):
	if role == "DOOR" and num == listener_num:
		visible = not state
		set_deferred("monitoring", not state)
		return
	if num != listener_num:
		return
	if rem_on_switch == 1 and state:
		queue_free()
		return
	if vis_on_switch == 1:
		visible = state
	if act_on_switch == 1:
		is_active = state
		set_deferred("monitoring", state)


func _on_body(body):
	if not is_active or not body.is_in_group("player"):
		return
	if role in ["COLLECTABLE", "POWERUP", "KEY"]:
		if role == "KEY":
			GameState.keys += 1
		if action_score != 0:
			GameState.add_score(action_score)
		if grant_gun:
			body.has_gun = true
		if popup_index > 0:
			GameState.show_popup(popup_index)
		if timer_id > 0:
			GameState.start_timer(timer_id, timer_secs)
		queue_free()
	elif role == "SWITCH" and not ignore_player:
		GameState.trigger_switch(switch_num, switch_mode)
		if popup_index > 0:
			GameState.show_popup(popup_index)
	elif role == "HURTING ZONE":
		GameState.damage_player(25)
	elif role == "TELEPORT START":
		var ends = get_tree().get_nodes_in_group("teleport_end")
		if ends.size() > 0:
			body.global_position = ends.front().global_position
	elif role == "FINISH LEVEL":
		get_tree().reload_current_scene()


func on_bullet_hit():
	if is_active and role == "SWITCH" and by_bullet:
		GameState.trigger_switch(switch_num, switch_mode)
		if popup_index > 0:
			GameState.show_popup(popup_index)


func on_melee_hit():
	if is_active and role == "SWITCH" and by_melee:
		GameState.trigger_switch(switch_num, switch_mode)
		if popup_index > 0:
			GameState.show_popup(popup_index)
""",

    "hud_widgets.gd": """extends Control

@export var widget_type: String = "HEALTH"
@export var timer_id: int = 1
@export var default_seconds: float = 10.0
@export var timer_param1: int = 0
@export var timer_song_stream: AudioStream

var time_left: float = 0.0
var running: bool = false


func _ready():
	if widget_type == "HEALTH":
		add_to_group("hud_health")
		update_hp(GameState.hp, GameState.max_hp)
	elif widget_type == "SCORE":
		add_to_group("hud_score")
		update_score(GameState.score)
	elif widget_type == "TIMER":
		add_to_group("game_timers")


func update_hp(cur: int, mx: int):
	if has_node("Bar"):
		$Bar.max_value = mx
		$Bar.value = cur


func update_score(val: int):
	if has_node("Lbl"):
		$Lbl.text = "SCORE: " + str(val)


func on_start_timer(tid: int, secs: float):
	if tid != timer_id:
		return
	time_left = secs if secs > 0 else default_seconds
	running = true
	visible = true


func _process(delta):
	if widget_type == "TIMER" and running:
		time_left -= delta
		if has_node("Lbl"):
			$Lbl.text = str(ceil(max(0.0, time_left)))
		if time_left <= 0.0:
			running = false
			if timer_song_stream != null:
				var bgm = get_tree().current_scene.get_node_or_null("BGM")
				if bgm != null:
					bgm.stream = timer_song_stream
					bgm.play()
			if timer_param1 > 0:
				GameState.trigger_switch(timer_param1, 1)
""",

    "player_master.gd": """extends CharacterBody2D

@export var mode: String = "platformer"
@export var speed: float = 300.0
@export var jump_force: float = -520.0
@export var has_gun: bool = false
@export var melee_damage: int = 10
@export var tex_idle: Texture2D
@export var frames_idle: int = 1
@export var tex_move: Texture2D
@export var frames_move: int = 1
@export var tex_jump: Texture2D
@export var frames_jump: int = 1
@export var tex_shoot: Texture2D
@export var frames_shoot: int = 1
@export var tex_melee: Texture2D
@export var frames_melee: int = 1
@export var tex_bullet: Texture2D

var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")
var facing: int = 1
var is_attacking: bool = false


func _ready():
	add_to_group("player")


func _set_anim(tex: Texture2D, f_count: int):
	if tex == null or not has_node("Sprite2D"):
		return
	var spr = $Sprite2D
	if spr.texture != tex:
		spr.texture = tex
		spr.hframes = max(1, f_count)
		spr.frame = 0


func _physics_process(delta):
	if mode == "shooter":
		var dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		velocity.x = speed * 0.8 + dir.x * (speed * 0.5)
		velocity.y = dir.y * speed
		move_and_slide()
		if (Input.is_action_just_pressed("ui_accept") or Input.is_key_pressed(KEY_Z) or Input.is_key_pressed(KEY_CTRL)) and not is_attacking:
			_shoot()
		return

	if mode == "rpg":
		var dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		velocity = dir * speed
		if dir.x != 0:
			facing = 1 if dir.x > 0 else -1
			$Sprite2D.flip_h = facing < 0
		_set_anim(tex_move, frames_move) if dir.length() > 0 else _set_anim(tex_idle, frames_idle)
		move_and_slide()
		return

	if not is_on_floor():
		velocity.y += gravity * delta

	if (Input.is_action_just_pressed("ui_accept") or Input.is_action_just_pressed("ui_up")) and is_on_floor():
		velocity.y = jump_force

	var direction = Input.get_axis("ui_left", "ui_right")
	if direction != 0:
		velocity.x = direction * speed
		facing = 1 if direction > 0 else -1
		$Sprite2D.flip_h = facing < 0
	else:
		velocity.x = move_toward(velocity.x, 0, speed)

	if has_gun and (Input.is_key_pressed(KEY_Z) or Input.is_key_pressed(KEY_CTRL)) and not is_attacking:
		_shoot()
	elif (Input.is_key_pressed(KEY_X) or Input.is_key_pressed(KEY_SHIFT)) and not is_attacking:
		_melee()

	if not is_attacking:
		if not is_on_floor() and tex_jump != null:
			_set_anim(tex_jump, frames_jump)
		elif direction != 0 and tex_move != null:
			_set_anim(tex_move, frames_move)
		else:
			_set_anim(tex_idle, frames_idle)

	move_and_slide()


func _shoot():
	is_attacking = true
	if tex_shoot != null:
		_set_anim(tex_shoot, frames_shoot)

	var b = Area2D.new()
	b.set_script(load("res://scripts/bullet.gd"))
	b.direction = facing
	b.global_position = global_position + Vector2(20 * facing, 10)

	var spr = Sprite2D.new()
	if tex_bullet != null:
		spr.texture = tex_bullet
	b.add_child(spr)

	var col = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(12, 8)
	col.shape = shape
	b.add_child(col)

	get_parent().add_child(b)

	await get_tree().create_timer(0.25).timeout
	is_attacking = false


func _melee():
	is_attacking = true
	if tex_melee != null:
		_set_anim(tex_melee, frames_melee)

	for body in get_tree().get_nodes_in_group("enemies"):
		if global_position.distance_to(body.global_position) < 65.0 and body.has_method("take_damage"):
			body.take_damage(melee_damage)

	for area in get_tree().get_nodes_in_group("switch_listeners"):
		if global_position.distance_to(area.global_position) < 65.0 and area.has_method("on_melee_hit"):
			area.on_melee_hit()

	await get_tree().create_timer(0.25).timeout
	is_attacking = false
""",
}


GAME_STATE_TEMPLATE = """extends Node

var switches: Dictionary = {{}}
var popups: Dictionary = {popups!r}
var hp: int = 100
var max_hp: int = 100
var score: int = 0
var keys: int = 0

var popup_panel: PanelContainer
var popup_label: Label
var is_popup_open: bool = false


func _ready():
	process_mode = Node.PROCESS_MODE_ALWAYS
	var layer = CanvasLayer.new()
	layer.layer = 50
	add_child(layer)

	popup_panel = PanelContainer.new()
	popup_panel.visible = false
	popup_panel.set_anchors_preset(Control.PRESET_CENTER)
	popup_panel.custom_minimum_size = Vector2(520, 220)
	popup_panel.offset_left = -260
	popup_panel.offset_top = -110
	popup_panel.offset_right = 260
	popup_panel.offset_bottom = 110
	layer.add_child(popup_panel)

	popup_label = Label.new()
	popup_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	popup_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	popup_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	popup_panel.add_child(popup_label)


func _process(_delta):
	if is_popup_open and Input.is_action_just_pressed("ui_accept"):
		popup_panel.visible = false
		is_popup_open = false
		get_tree().paused = false


func show_popup(idx: int):
	if idx <= 0 or not popups.has(idx):
		return
	popup_label.text = "\\n".join(popups[idx])
	popup_panel.visible = true
	is_popup_open = true
	get_tree().paused = true


func trigger_switch(num: int, mode: int = 2):
	if num <= 0:
		return
	var nxt = not switches.get(num, false) if mode == 2 else true
	switches[num] = nxt
	get_tree().call_group("switch_listeners", "on_switch_event", num, nxt)


func start_timer(tid: int, secs: float):
	if tid > 0:
		get_tree().call_group("game_timers", "on_start_timer", tid, secs)


func add_score(pts: int):
	score += pts
	get_tree().call_group("hud_score", "update_score", score)


func damage_player(dmg: int):
	hp = max(0, hp - dmg)
	get_tree().call_group("hud_health", "update_hp", hp, max_hp)
	if hp <= 0:
		hp = max_hp
		get_tree().reload_current_scene()
"""


def write_gd_scripts(popups: dict[int, list[str]]):
    out_dir = os.path.join(GODOT_DIR, "scripts")
    os.makedirs(out_dir, exist_ok=True)

    for fname, code in SCRIPTS.items():
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)

    gs_code = GAME_STATE_TEMPLATE.format(popups=popups)
    with open(os.path.join(out_dir, "GameState.gd"), "w", encoding="utf-8") as f:
        f.write(gs_code)