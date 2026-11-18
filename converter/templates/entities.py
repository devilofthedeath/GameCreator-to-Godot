import os
from converter.config import GODOT_DIR

ENTITIES_SCRIPTS = {
    "anim_sprite.gd": """extends Sprite2D
@export var fps: float = 10.0
@export var freeze_last: bool = false
var timer: float = 0.0

func _process(delta):
	if hframes <= 1:
		return
	timer += delta
	# Оригинальные 20 fps выглядят слишком дёргано — ограничиваем 12.
	var rate = min(max(1.0, fps), 12.0)
	if timer >= 1.0 / rate:
		timer = 0.0
		if freeze_last and frame >= hframes - 1:
			return
		frame = (frame + 1) % hframes
""",
    "bullet.gd": """extends Area2D

@export var team: String = "enemy"
@export var velocity: Vector2 = Vector2(100, 0)
@export var damage: int = 10
@export var lifetime: float = 2.0

var owner_ref: Node = null
var owner_id: String = ""


func _ready():
	add_to_group("bullets")
	body_entered.connect(_on_body)
	area_entered.connect(_on_area)
	await get_tree().create_timer(max(0.05, lifetime)).timeout
	queue_free()


func _physics_process(delta):
	global_position += velocity * delta


func _on_body(body):
	if body == owner_ref:
		return
	if team == "player" and body.is_in_group("enemies") and body.has_method("take_damage"):
		body.take_damage(damage)
		queue_free()
		return
	if team == "enemy" and body.is_in_group("player") and body.has_method("take_damage"):
		body.take_damage(damage)
		queue_free()
		return
	if team == "player" and body.is_in_group("destroyables") and body.has_method("take_damage"):
		body.take_damage(damage)
		queue_free()
		return
	if body.is_in_group("blocks") or body.is_in_group("pushables"):
		# Неподвижная пуля — это мина, она должна лежать на полу и
		# подрывать врагов, а не ломаться о блоки.
		if velocity.length() > 0.0:
			queue_free()


func _on_area(area):
	if area.has_method("on_bullet_hit"):
		area.on_bullet_hit()
		queue_free()
""",
    "enemy.gd": """extends CharacterBody2D

@export var mode: String = "platformer"
@export var speed: float = 90.0
@export var max_hp: int = 30
@export var hp: int = 30
@export var infinite_health: bool = false
@export var contact_damage: int = 10
@export var use_gravity: bool = true
@export var move_dir_mode: int = 1
@export var move_shape: int = 0
@export var towards_player: int = 0
@export var random_direction: int = 0
@export var ignore_objects: bool = false
@export var turn_to_player: int = 0
@export var boss: bool = false
@export var phase: int = 0
@export var can_shoot: bool = false
@export var shoot_dir: int = 0
@export var bullet_speed: float = 300.0
@export var bullet_damage: int = 10
@export var bullet_max_count: int = 1
@export var bullet_lifetime: float = 2.0
@export var shoot_interval: float = 1.0
@export var bullet_tex: Texture2D
@export var bullet_shape: Vector2 = Vector2(10, 8)
@export var gc_id: String = ""
@export var death_switch: int = 0
@export var show_health_bar: bool = false
@export var health_bar_width: int = 40
@export var health_bar_height: int = 6
@export var health_bar_color: Color = Color(0.9, 0.2, 0.2, 1)
@export var health_bar_offset: float = -20.0
@export var start_visible: bool = true
@export var start_active: bool = true
@export var listener_num: int = 0
@export var vis_on_switch: int = 0
@export var act_on_switch: int = 0
@export var rem_on_switch: int = 0

var dir: int = -1
var move_vec: Vector2 = Vector2.LEFT
var random_timer: float = 0.0
var is_active: bool = true
var is_aggro: bool = false
var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")
var shoot_timer: float = 0.0
var contact_timer: float = 0.0
var age: float = 0.0
var origin: Vector2 = Vector2.ZERO
var hp_bar: ProgressBar = null


func _ready():
	visible = start_visible
	is_active = start_active
	origin = global_position
	shoot_timer = randf() * max(0.1, shoot_interval)
	if listener_num > 0:
		add_to_group("switch_listeners")
	if ignore_objects:
		collision_mask = 0  # проходит сквозь стены и объекты
	if show_health_bar:
		_make_hp_bar()


func _make_hp_bar():
	hp_bar = ProgressBar.new()
	hp_bar.custom_minimum_size = Vector2(health_bar_width, health_bar_height)
	hp_bar.position = Vector2(-health_bar_width / 2.0, health_bar_offset)
	hp_bar.min_value = 0.0
	hp_bar.max_value = max(1.0, float(max_hp))
	hp_bar.value = hp
	hp_bar.show_percentage = false
	var sb = StyleBoxFlat.new()
	sb.bg_color = health_bar_color
	hp_bar.add_theme_stylebox_override("fill", sb)
	add_child(hp_bar)


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
	age += delta
	shoot_timer -= delta
	contact_timer -= delta

	var players = get_tree().get_nodes_in_group("player")
	var player = players.front() if players.size() > 0 else null

	if mode == "shooter":
		_shooter_move(player)
	else:
		_generic_move(delta, player)

	_try_shoot(player)
	_check_contact()


func _shooter_move(player):
	# Траектории скроллер-шутера: 0 - статика, 1 - синус X, 2 - синус Y,
	# 3 - круг, 4 - босс (медленно следует за игроком по вертикали).
	var drift := -speed * 0.15
	if move_shape == 0:
		velocity = Vector2.ZERO
	elif move_shape == 1:
		velocity = Vector2(drift, cos(age * 1.4) * speed * 0.3)
	elif move_shape == 2:
		velocity = Vector2(drift * 0.2, sin(age * 1.4) * speed * 0.5)
	elif move_shape == 3:
		velocity = Vector2(drift * 0.3 + cos(age) * speed * 0.25, sin(age) * speed * 0.4)
	elif move_shape == 4:
		var target_y = origin.y
		if player != null and turn_to_player == 1:
			target_y = player.global_position.y
		velocity = Vector2(drift * 0.2, clamp((target_y - global_position.y) * 0.6, -speed * 0.3, speed * 0.3))
	else:
		velocity = Vector2(drift, 0)
	if ignore_objects:
		position += velocity * get_physics_process_delta_time()
	else:
		move_and_slide()
	if has_node("Sprite2D") and player != null:
		$Sprite2D.flip_h = player.global_position.x < global_position.x


func _generic_move(delta, player):
	var v := Vector2.ZERO
	if towards_player == 1 and player != null:
		var d = player.global_position - global_position
		if mode == "platformer":
			v = Vector2(sign(d.x), 0) * speed
		else:
			v = d.normalized() * speed if d.length() > 2.0 else Vector2.ZERO
	elif random_direction == 1 or move_dir_mode == 3:
		random_timer -= delta
		if random_timer <= 0.0:
			random_timer = randf_range(0.8, 2.2)
			move_vec = Vector2.RIGHT.rotated(randf() * TAU)
		v = move_vec * speed
	elif move_dir_mode == 2:
		v = Vector2(0, dir) * speed
	elif move_dir_mode == 1:
		v = Vector2(dir, 0) * speed

	if ignore_objects:
		velocity = v
		position += velocity * delta
	else:
		if move_dir_mode == 2 and mode != "platformer":
			velocity.y = v.y
			velocity.x = 0.0
		elif mode == "platformer":
			velocity.x = v.x
			if use_gravity and not is_on_floor():
				velocity.y += gravity * delta
		else:
			velocity.x = v.x
			velocity.y = v.y
		move_and_slide()
		if is_on_wall():
			dir *= -1
			move_vec = -move_vec

	if has_node("Sprite2D") and abs(v.x) > 1.0:
		$Sprite2D.flip_h = v.x > 0


func _try_shoot(player):
	if not can_shoot or shoot_timer > 0.0:
		return
	var count := 0
	for b in get_tree().get_nodes_in_group("bullets"):
		if b.get("owner_id") == gc_id:
			count += 1
	if count >= max(1, bullet_max_count):
		return

	var aim := Vector2.ZERO
	if shoot_dir == 1:
		aim = Vector2.LEFT
	elif shoot_dir == 2:
		aim = Vector2.RIGHT
	elif shoot_dir == 3:
		aim = Vector2.DOWN
	elif shoot_dir == 4:
		aim = Vector2.UP
	elif turn_to_player == 1 and player != null:
		var d = player.global_position - global_position
		aim = d.normalized() if d.length() > 0.01 else Vector2.DOWN
	elif speed > 0.0 and abs(velocity.x) > 1.0:
		aim = Vector2(sign(velocity.x), 0)
	else:
		aim = Vector2.DOWN

	shoot_timer = max(0.1, shoot_interval)
	var b = Area2D.new()
	b.set_script(load("res://scripts/bullet.gd"))
	b.team = "enemy"
	b.owner_ref = self
	b.owner_id = gc_id
	b.damage = bullet_damage
	b.lifetime = bullet_lifetime
	b.velocity = aim * bullet_speed
	b.global_position = global_position + aim * 20.0
	b.rotation = aim.angle()

	if bullet_tex != null:
		var spr = Sprite2D.new()
		spr.texture = bullet_tex
		spr.centered = true
		b.add_child(spr)

	var col = CollisionShape2D.new()
	var sh = RectangleShape2D.new()
	sh.size = bullet_shape
	col.shape = sh
	b.add_child(col)
	get_parent().add_child(b)


func _check_contact():
	if contact_damage <= 0 or contact_timer > 0.0:
		return
	var players = get_tree().get_nodes_in_group("player")
	if players.is_empty():
		return
	var player = players[0]
	if global_position.distance_to(player.global_position) < 42.0 and player.has_method("take_damage"):
		player.take_damage(contact_damage)
		contact_timer = 0.6


func take_damage(amount: int, _from_pos = null):
	if not is_active:
		return
	if not infinite_health:
		hp -= amount
	if hp_bar != null:
		hp_bar.value = max(0, hp)
	is_aggro = true
	modulate = Color(1, 0.3, 0.3)
	await get_tree().create_timer(0.1).timeout
	modulate = Color(1, 1, 1)
	if not infinite_health and hp <= 0:
		if death_switch > 0:
			GameState.trigger_switch(death_switch, 1)
		if gc_id != "":
			GameState.mark_cleared(gc_id)
		if boss and phase == 0:
			var clone = duplicate()
			clone.phase = 1
			clone.hp = max_hp
			clone.start_active = true
			get_parent().add_child(clone)
			clone.global_position = global_position + Vector2(0.0, -180.0)
		queue_free()
""",
    "destroyable.gd": """extends StaticBody2D

@export var max_hp: int = 1
@export var hp: int = 1
@export var infinite_health: bool = false
@export var destroy_score: int = 0
@export var destroy_switch: int = 0
@export var ignore_bullets: bool = false
@export var destroy_tex: Texture2D
@export var gc_id: String = ""
@export var start_visible: bool = true
@export var start_active: bool = true
@export var listener_num: int = 0
@export var vis_on_switch: int = 0
@export var act_on_switch: int = 0
@export var rem_on_switch: int = 0

var is_dead: bool = false


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


func take_damage(amount: int, _from = null):
	if is_dead or not start_active or ignore_bullets:
		return
	if not infinite_health:
		hp -= amount
	if infinite_health or hp > 0:
		return
	is_dead = true
	if destroy_score > 0:
		GameState.add_score(destroy_score)
	if destroy_switch > 0:
		GameState.trigger_switch(destroy_switch, 1)
	if gc_id != "":
		GameState.mark_cleared(gc_id)
	if destroy_tex != null and has_node("Sprite2D"):
		$Sprite2D.texture = destroy_tex
		$Sprite2D.hframes = 1
	if has_node("CollisionShape2D"):
		$CollisionShape2D.set_deferred("disabled", true)
	if has_node("Sprite2D"):
		$Sprite2D.visible = false
	await get_tree().create_timer(0.15).timeout
	queue_free()
""",
    "pushable.gd": """extends CharacterBody2D

@export var pushed_switch: int = 0
@export var gc_id: String = ""
@export var start_visible: bool = true
@export var listener_num: int = 0
@export var rem_on_switch: int = 0
@export var use_gravity: bool = true

var gravity = ProjectSettings.get_setting("physics/2d/default_gravity")
var origin: Vector2 = Vector2.ZERO
var triggered: bool = false


func _ready():
	visible = start_visible
	origin = global_position
	if listener_num > 0:
		add_to_group("switch_listeners")


func on_switch_event(num: int, state: bool):
	if num == listener_num and state:
		global_position = origin
		velocity = Vector2.ZERO
		triggered = false


func _physics_process(delta):
	if use_gravity and not is_on_floor():
		velocity.y += gravity * delta
	elif is_on_floor():
		velocity.y = 0.0

	# Толкаем ящик, когда игрок упирается в него. Не опираемся на slide-коллизии:
	# неподвижный CharacterBody2D их не получает, поэтому проверяем игрока рядом.
	var push := 0.0
	for body in get_tree().get_nodes_in_group("player"):
		var dx = global_position.x - body.global_position.x
		var dy = abs(global_position.y - body.global_position.y)
		if abs(dx) < 62.0 and dy < 62.0 and sign(body.velocity.x) == sign(dx) and abs(body.velocity.x) > 1.0:
			push = sign(dx) * abs(body.velocity.x) * 0.8
	if abs(push) > 1.0:
		velocity.x = push
	else:
		velocity.x = move_toward(velocity.x, 0.0, 400.0 * delta)
	move_and_slide()

	if not triggered and global_position.distance_to(origin) > 40.0:
		triggered = true
		if pushed_switch > 0:
			GameState.trigger_switch(pushed_switch, 1)
		if gc_id != "":
			GameState.mark_cleared(gc_id)
""",
    "bg_scroll.gd": """extends Node2D

@export var scroll_factor: float = 1.0


func _process(_delta):
	if scroll_factor <= 0.0:
		position = Vector2.ZERO
		return
	# Берём именно canvas-трансформу: она учитывает сглаживание камеры,
	# поэтому фон не «дёргается» относительно мира.
	position = -get_viewport().get_canvas_transform().origin * scroll_factor
""",
    "level_bounds.gd": """extends Node

@export var level_width: int = 480
@export var level_height: int = 320


func _ready():
	await get_tree().process_frame
	var players = get_tree().get_nodes_in_group("player")
	if players.is_empty():
		return
	var cam = players[0].get_node_or_null("Camera2D")
	if cam == null:
		return
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = level_width
	cam.limit_bottom = level_height
	GameState.level_bottom = level_height + 120
""",
    "solid_block.gd": """extends StaticBody2D

@export var start_visible: bool = true
@export var start_active: bool = true
@export var listener_num: int = 0
@export var vis_on_switch: int = 0
@export var act_on_switch: int = 0
@export var rem_on_switch: int = 0
@export var enable_move: bool = false
@export var move_speed: float = 0.0
@export var move_direction: int = 1

var moving: bool = false


func _ready():
	visible = start_visible
	# Невидимая стена остаётся твёрдой — выключаем только отрисовку.
	if has_node("CollisionShape2D"):
		$CollisionShape2D.set_deferred("disabled", not start_active)
	if listener_num > 0 or enable_move:
		add_to_group("switch_listeners")
	if enable_move and listener_num == 0:
		moving = true


func on_switch_event(num: int, state: bool):
	if enable_move and state and (num == listener_num or listener_num == 0):
		moving = true
	if num != listener_num:
		return
	if rem_on_switch == 1 and state:
		queue_free()
		return
	if vis_on_switch == 1:
		visible = state
	if act_on_switch == 1 and has_node("CollisionShape2D"):
		$CollisionShape2D.set_deferred("disabled", not state)


# Свитч, включивший движение, может стоять прямо на блоке (например, знак
# вопроса над скейтом) — включаем платформу по соседству, а не только по номеру.
func on_nearby_switch(pos: Vector2, _num: int):
	if enable_move and global_position.distance_to(pos) < 70.0:
		moving = true


func _physics_process(delta):
	if moving and move_speed > 0.0:
		position.x += move_direction * move_speed * delta
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
@export var action_health: int = 0
@export var damage: int = 25
@export var popup_index: int = 0
@export var grant_gun: bool = false
@export var timer_id: int = 0
@export var timer_secs: float = 0.0
@export var activated_tex: Texture2D
@export var once: bool = false
@export var need_score: int = 0
@export var need_cleared: String = ""
@export var gc_id: String = ""

var is_active: bool = true
var switched: bool = false
var finish_done: bool = false


func _ready():
	visible = start_visible
	is_active = start_active
	set_deferred("monitoring", start_active)
	if listener_num > 0 or role == "DOOR" or role == "SWITCH":
		add_to_group("switch_listeners")
	body_entered.connect(_on_body)


func on_switch_event(num: int, state: bool):
	if role == "DOOR" and num == listener_num:
		visible = not state
		set_deferred("monitoring", not state)
		return
	# Сам переключатель меняет спрайт, когда срабатывает его номер.
	if role == "SWITCH" and num == switch_num:
		_set_switched(state)
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


func _set_switched(state: bool):
	switched = state
	if activated_tex != null and has_node("Sprite2D"):
		$Sprite2D.texture = activated_tex
		$Sprite2D.hframes = 1


func _activate_switch():
	if not is_active or (once and switched):
		return
	GameState.trigger_switch(switch_num, switch_mode)
	get_tree().call_group("moving_blocks", "on_nearby_switch", global_position, switch_num)
	if popup_index > 0:
		GameState.show_popup(popup_index)


func _can_finish() -> bool:
	if need_score > 0 and GameState.score < need_score:
		return false
	if need_cleared != "" and not GameState.is_cleared(need_cleared):
		return false
	return true


# У уровней 3–5 финиш висит в воздухе, но должен срабатывать сразу после
# убийства нужного врага (check_type_cleared) — без прикосновения к зоне.
func _process(_delta):
	if role == "FINISH LEVEL" and not finish_done and need_cleared != "" and _can_finish():
		finish_done = true
		GameState.next_level()


func _on_body(body):
	if not is_active or not body.is_in_group("player"):
		return
	if role in ["COLLECTABLE", "POWERUP", "KEY", "BONUS"]:
		if role == "KEY":
			GameState.keys += 1
		if action_score != 0:
			GameState.add_score(action_score)
		if action_health > 0 and body.has_method("heal"):
			body.heal(action_health)
		if grant_gun:
			body.has_gun = true
		if popup_index > 0:
			GameState.show_popup(popup_index)
		if timer_id > 0:
			GameState.start_timer(timer_id, timer_secs)
		if gc_id != "":
			GameState.mark_cleared(gc_id)
		queue_free()
	elif role == "SWITCH" and not ignore_player:
		_activate_switch()
	elif role == "HURTING ZONE":
		if body.has_method("take_damage"):
			body.take_damage(damage)
	elif role == "TELEPORT START":
		var ends = get_tree().get_nodes_in_group("teleport_end")
		if ends.size() > 0:
			body.global_position = ends.front().global_position
	elif role == "FINISH LEVEL":
		if _can_finish():
			GameState.next_level()


func on_bullet_hit():
	# В оригинале переключатели часто срабатывают выстрелом даже без явного флага.
	if role == "SWITCH":
		_activate_switch()


func on_melee_hit():
	if role == "SWITCH":
		_activate_switch()
""",
}


def write_entity_scripts():
    out_dir = os.path.join(GODOT_DIR, "scripts")
    for fname, code in ENTITIES_SCRIPTS.items():
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write(code)
