import glob
import os

from converter.config import RAW_DIR, GODOT_DIR, get_gc_color, parse_obj_file
from converter.settings import (
    COORD_SCALE, MOVE_SPEED_SCALE, BULLET_SPEED_SCALE, MAX_ANIM_FPS,
)

COORD_SCALE_FALLBACK = COORD_SCALE


def _obj_family(obj_type: str) -> str:
    """Жанр игры, к которому относится объект (по его внутреннему имени)."""
    t = obj_type.lower()
    if "scrollershooter" in t:
        return "shooter"
    if "topview" in t:
        return "topview"
    if "rpg" in t:
        return "rpg"
    return "platformer"


def _prop(props: dict, *keys, default="0"):
    """Первое найденное свойство. У разных жанров имена ключей отличаются."""
    for key in keys:
        if key in props:
            return props[key]
    return default


def _fnum(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _inum(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _build_hud_tscn(
    obj_id: str,
    role: str,
    props: dict,
    audio_files: dict,
    s_vis: str,
    z_idx: int,
) -> str:
    tcol = get_gc_color(props.get("base_color", "233"))

    if role == "HEALTH":
        bw = int(props.get("health_bar_width", "100"))
        bh = max(10, int(props.get("health_bar_height", "12")))
        bcol = get_gc_color(
            props.get("health_bar_color", "110"),
            "Color(0.9, 0.2, 0.2, 1)",
        )
        return "\n".join([
            "[gd_scene load_steps=3 format=3]",
            '[ext_resource type="Script" path="res://scripts/hud_widgets.gd" id="1"]',
            '[sub_resource type="StyleBoxFlat" id="2"]',
            f"bg_color = {bcol}",
            f'[node name="Obj_{obj_id}" type="Control"]',
            'script = ExtResource("1")',
            '[node name="Bar" type="ProgressBar" parent="."]',
            f"custom_minimum_size = Vector2({bw}, {bh})",
            'theme_override_styles/fill = SubResource("2")',
            "value = 100.0",
            "show_percentage = false",
        ]) + "\n"

    if role == "SCORE":
        return "\n".join([
            "[gd_scene load_steps=2 format=3]",
            '[ext_resource type="Script" path="res://scripts/hud_widgets.gd" id="1"]',
            f'[node name="Obj_{obj_id}" type="Control"]',
            'script = ExtResource("1")',
            'widget_type = "SCORE"',
            '[node name="Lbl" type="Label" parent="."]',
            f"theme_override_colors/font_color = {tcol}",
            'text = "SCORE: 0"',
        ]) + "\n"

    if role == "TIMER":
        tid = _inum(props.get("timer_id", "1"))
        tsec = _fnum(props.get("timer_seconds", "10"))
        tp1 = _inum(props.get("timer_param1", "0"))
        action = _inum(props.get("timer_action", "1"))
        listener = _inum(props.get("listener", "0"))
        tsong = props.get("timer_song", "")
        has_snd = tsong in audio_files and tsong != "-1"
        ext = ['[ext_resource type="Script" path="res://scripts/hud_widgets.gd" id="1"]']
        if has_snd:
            ext.append(f'[ext_resource type="AudioStream" path="res://audio/{audio_files[tsong]}" id="2"]')
        subs = []
        node_lines = [
            f'[node name="Obj_{obj_id}" type="Control"]',
            f"visible = {s_vis}",
            'script = ExtResource("1")',
            'widget_type = "TIMER"',
            f"timer_id = {tid}",
            f"default_seconds = {tsec}",
            f"timer_param1 = {tp1}",
            f"timer_action = {action}",
            f"listener_num = {listener}",
            f"auto_start = {str(props.get('active', '1') == '1' and listener == 0).lower()}",
        ]
        if has_snd:
            node_lines.append('timer_song_stream = ExtResource("2")')
        if props.get("timer_bar", "0") == "1":
            bcol = get_gc_color(props.get("timer_bar_color", "4"))
            subs.extend([
                '[sub_resource type="StyleBoxFlat" id="tb"]',
                f"bg_color = {bcol}",
            ])
            node_lines.extend([
                '[node name="Bar" type="ProgressBar" parent="."]',
                f"custom_minimum_size = Vector2({_inum(props.get('timer_bar_width', '100'))}, {max(6, _inum(props.get('timer_bar_height', '6')))})",
                'theme_override_styles/fill = SubResource("tb")',
                "value = 100.0",
            ])
        node_lines.extend([
            '[node name="Lbl" type="Label" parent="."]',
            f"theme_override_colors/font_color = {tcol}",
            f'text = "{int(tsec)}"',
        ])
        lines = [f"[gd_scene load_steps={len(ext) + len(subs) + 1} format=3]", *ext, *subs, *node_lines]
        return "\n".join(lines) + "\n"

    tval = props.get("text", "").replace('"', "'")
    return "\n".join([
        "[gd_scene format=3]",
        f'[node name="Obj_{obj_id}" type="Label"]',
        f"z_index = {z_idx + 10}",
        f"theme_override_colors/font_color = {tcol}",
        f'text = "{tval}"',
    ]) + "\n"


def _build_player_tscn(
    obj_id: str,
    obj_type: str,
    props: dict,
    sprite_info: dict,
    z_idx: int,
    fps: float,
) -> str:
    fname, frames, fw, fh, (bl, bt, br, bb) = sprite_info[props["main_sprite"]]
    cx, cy = (bl + br) / 2.0, (bt + bb) / 2.0

    family = _obj_family(obj_type)
    mode = "shooter" if family == "shooter" else (
        "rpg" if family in ("rpg", "topview") else "platformer"
    )
    # У скроллер-шутера и RPG параметры пуль лежат в ключах levelN_* / *_*_lvN.
    has_gun = _prop(props, "has_gun", "level1_gun", "has_gun_lv1", "level2_gun", default="0") == "1"
    spd = _fnum(_prop(props, "move_speed", "level1_speed", default="10")) * MOVE_SPEED_SCALE
    jmp = -_fnum(props.get("jump_strength", "12")) * 43.0
    bspd_raw = _fnum(_prop(props, "bullet_speed", "level1_bullet_speed", "bullet_speed_lv1", default="12"))
    # 0 в оригинале означает НЕ "по умолчанию", а неподвижный объект
    # (например, "какашку", которую игрок оставляет под собой).
    bspd = bspd_raw * BULLET_SPEED_SCALE if bspd_raw > 0 else 0.0
    bx = _fnum(props.get("bullet_x_position", "0")) / COORD_SCALE_FALLBACK
    by = _fnum(props.get("bullet_y_position", "0")) / COORD_SCALE_FALLBACK
    if bspd_raw == 0:
        # Мина ставится строго под центром игрока (не в сторону).
        bx, by = 0.0, max(10.0, fh - cy)
    bullet_shape = (12.0, 8.0)
    mdmg = _inum(_prop(props, "melee_damage", "melee_damage_lv1", default="10"))
    bdamage = _inum(_prop(props, "bullet_damage", "level1_bullet_damage", "bullet_damage_lv1", default="15"))
    bmax = max(1, _inum(_prop(props, "bullet_max_count", "level1_bullet_max_count", "bullet_max_count_lv1", default="1")))
    blife = _fnum(_prop(props, "bullet_lifetime", "level1_bullet_lifetime", "bullet_lifetime_lv1", default="2")) or 2.0
    shoot_dir = _inum(props.get("shooting_direction", "0"))
    max_hp = _inum(props.get("new_health", "100")) if props.get("overwrite_health", "0") == "1" else 100
    bullet_in_air = props.get("bullet_in_air", "0") == "1"

    ex_res = []
    ex_pr = ['tex_idle = ExtResource("1")', f"frames_idle = {frames}"]
    r_i = 4

    anim_map = [
        (["move_sprite", "move_leftright_sprite"], "tex_move", "frames_move"),
        (["jump_sprite"], "tex_jump", "frames_jump"),
        (["shoot_sprite", "shoot_leftright_sprite"], "tex_shoot", "frames_shoot"),
        (["melee_sprite", "melee_leftright_sprite"], "tex_melee", "frames_melee"),
        (["bullet_sprite", "level1_bullet_sprite", "bullet_sprite_lv1"], "tex_bullet", None),
        (["shoot_air_sprite"], "tex_shoot_air", "frames_shoot_air"),
        (["melee_air_sprite"], "tex_melee_air", "frames_melee_air"),
    ]
    for pks, ptex, pfr in anim_map:
        for pk in pks:
            sid = props.get(pk, "-1")
            if sid in sprite_info:
                fn, fc, _, _, sbox = sprite_info[sid]
                if ptex == "tex_bullet":
                    bullet_shape = (max(4, sbox[2] - sbox[0]), max(4, sbox[3] - sbox[1]))
                ex_res.append(
                    f'[ext_resource type="Texture2D" path="res://sprites/{fn}" id="{r_i}"]'
                )
                ex_pr.append(f'{ptex} = ExtResource("{r_i}")')
                if pfr:
                    ex_pr.append(f"{pfr} = {fc}")
                r_i += 1
                break

    lines = [
        f"[gd_scene load_steps={r_i + 1} format=3]",
        f'[ext_resource type="Texture2D" path="res://sprites/{fname}" id="1"]',
        '[ext_resource type="Script" path="res://scripts/player_master.gd" id="2"]',
        '[ext_resource type="Script" path="res://scripts/anim_sprite.gd" id="3"]',
        *ex_res,
        '[sub_resource type="RectangleShape2D" id="sh"]',
        f"size = Vector2({max(8, br - bl)}, {max(8, bb - bt)})",
        f'[node name="Obj_{obj_id}" type="CharacterBody2D" groups=["player"]]',
        f"z_index = {z_idx + 5}",
        'script = ExtResource("2")',
        f'mode = "{mode}"',
        f"speed = {spd}",
        f"jump_force = {jmp}",
        f"has_gun = {str(has_gun).lower()}",
        f"shoot_dir = {shoot_dir}",
        f"bullet_speed = {bspd}",
        f"bullet_damage = {bdamage}",
        f"bullet_max_count = {bmax}",
        f"bullet_lifetime = {blife}",
        f"bullet_offset = Vector2({bx}, {by})",
        f"bullet_shape = Vector2({bullet_shape[0]}, {bullet_shape[1]})",
        f"body_center = Vector2({cx}, {cy})",
        f'bullet_owner_id = "{obj_id}"',
        f"bullet_in_air = {str(bullet_in_air).lower()}",
        f"melee_damage = {mdmg}",
        f"max_hp = {max_hp}",
        f"jump_freeze = {str(props.get('jump_sprite_freeze', '0') == '1').lower()}",
        *ex_pr,
        '[node name="Sprite2D" type="Sprite2D" parent="."]',
        'texture = ExtResource("1")',
        "centered = false",
        f"modulate = Color(1, 1, 1, {max(0.0, min(1.0, _fnum(props.get('alpha', '100')) / 100.0)):.3f})",
        f"hframes = {frames}",
        'script = ExtResource("3")',
        f"fps = {fps}",
        '[node name="CollisionShape2D" type="CollisionShape2D" parent="."]',
        f"position = Vector2({cx}, {cy})",
        'shape = SubResource("sh")',
        '[node name="Camera2D" type="Camera2D" parent="."]',
        f"position = Vector2({cx}, {cy})",
    ]
    return "\n".join(lines) + "\n"


def build_objects(sprite_info: dict, audio_files: dict) -> tuple[set, set]:
    created_objs, fixed_hud = set(), set()
    out_dir = os.path.join(GODOT_DIR, "objects")
    os.makedirs(out_dir, exist_ok=True)

    for obj_path in glob.glob(os.path.join(RAW_DIR, "*.obj")):

        obj_type, obj_role, props = parse_obj_file(obj_path)
        if not props or obj_role == "POPUP" or "BUTTON" in obj_role:
            continue

        obj_id = os.path.basename(obj_path).replace(".obj", "")
        if obj_role in ["HEALTH", "SCORE", "TIMER"] or (obj_role == "TEXT" and props.get("fixed", "0") == "1"):
            fixed_hud.add(obj_id)

        spr_id = props.get("main_sprite", "-1")
        # Godot 4 ограничивает z_index диапазоном [-4096, 4096],
        # а в оригинале depth бывает 10000 и 1000000.
        z_idx = max(-4000, min(4000, _inum(props.get("depth", "0"))))
        fps = min(MAX_ANIM_FPS, _fnum(props.get("animation_speed", "10"), 10.0))
        s_vis = "true" if props.get("visible", "1") == "1" else "false"
        s_act = "true" if props.get("active", "1") == "1" else "false"
        l_num = int(props.get("listener", "0"))
        v_sw = int(props.get("visible_when_switched", "0"))
        a_sw = int(props.get("activate_when_switched", "0"))
        r_sw = int(props.get("remove_when_switched", "0"))

        is_player = obj_role == "PLAYER" or obj_type.endswith("_player")
        is_destroyable = obj_role == "DESTROYABLE BLOCK"
        is_pushable = obj_role == "PUSHABLE OBJECT"
        is_solid = obj_role == "BLOCK" or ("_block" in obj_type and not is_destroyable)
        is_enemy = obj_role in ["ENEMY", "MONSTER"]
        has_tex = spr_id in sprite_info

        if obj_role in ["HEALTH", "SCORE", "TIMER", "TEXT"]:
            tscn = _build_hud_tscn(obj_id, obj_role, props, audio_files, s_vis, z_idx)
        elif is_player and has_tex:
            tscn = _build_player_tscn(obj_id, obj_type, props, sprite_info, z_idx, fps)
        else:
            if has_tex:
                fname, frames, fw, fh, (bl, bt, br, bb) = sprite_info[spr_id]
            else:
                fname, frames, fw, fh, (bl, bt, br, bb) = ("", 1, 40, 40, (0, 0, 40, 40))
            cx, cy = (bl + br) / 2.0, (bt + bb) / 2.0
            # Сплошные блоки (и невидимые стены) имеют коллизию по всему кадру,
            # остальные объекты — по непрозрачным пикселям спрайта.
            shape_cx, shape_cy = (fw / 2.0, fh / 2.0) if (is_destroyable or is_pushable) else (cx, cy)
            common_props = [
                f"start_visible = {s_vis}",
                f"start_active = {s_act}",
                f"listener_num = {l_num}",
                f"vis_on_switch = {v_sw}",
                f"act_on_switch = {a_sw}",
                f"rem_on_switch = {r_sw}",
            ]

            lines = [f"[gd_scene load_steps={5 if has_tex else 3} format=3]"]
            if has_tex:
                lines.append(
                    f'[ext_resource type="Texture2D" path="res://sprites/{fname}" id="1"]'
                )
                lines.append(
                    '[ext_resource type="Script" path="res://scripts/anim_sprite.gd" id="3"]'
                )

            if is_solid:
                lines.append(
                    '[ext_resource type="Script" path="res://scripts/solid_block.gd" id="2"]'
                )
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({max(4, br - bl)}, {max(4, bb - bt)})",
                ])
                can_move = props.get("enable_move", "0") == "1"
                block_extra = []
                if can_move:
                    block_extra.extend([
                        f"enable_move = true",
                        f"move_speed = {_fnum(props.get('move_speed', '0')) * MOVE_SPEED_SCALE}",
                        f"move_direction = {1 if _inum(props.get('move_direction', '1')) in (0, 1, 2) else -1}",
                    ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="StaticBody2D" groups=["blocks"{", \"moving_blocks\"" if can_move else ""}]]',
                    f"z_index = {z_idx}",
                    'script = ExtResource("2")',
                    *block_extra,
                    *common_props,
                ])
            elif is_destroyable:
                lines.append('[ext_resource type="Script" path="res://scripts/destroyable.gd" id="2"]')
                dprops = []
                dsid = props.get("destroy_sprite", "-1")
                if dsid in sprite_info and dsid != spr_id:
                    dfn = sprite_info[dsid][0]
                    # ext_resource идут раньше sub_resource
                    lines.insert(3, f'[ext_resource type="Texture2D" path="res://sprites/{dfn}" id="4"]')
                    dprops.append('destroy_tex = ExtResource("4")')
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({fw}, {fh})",
                ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="StaticBody2D" groups=["blocks", "destroyables"]]',
                    f"z_index = {z_idx}",
                    'script = ExtResource("2")',
                    f"max_hp = {max(1, _inum(props.get('self_health', '1')))}",
                    f"hp = {max(1, _inum(props.get('self_health', '1')))}",
                    f"infinite_health = {str(props.get('infinite_health', '0') == '1').lower()}",
                    f"destroy_score = {_inum(props.get('action_score', '0'))}",
                    f"destroy_switch = {_inum(props.get('activate_destroyed_switch_number', '0')) if props.get('activate_destroyed_switch', '0') == '1' else 0}",
                    f'gc_id = "{obj_id}"',
                    f"ignore_bullets = {str(props.get('ignore_bullets', '0') == '1').lower()}",
                    *dprops,
                    *common_props,
                ])
            elif is_pushable:
                family = _obj_family(obj_type)
                lines.append('[ext_resource type="Script" path="res://scripts/pushable.gd" id="2"]')
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({fw}, {fh})",
                ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="CharacterBody2D" groups=["pushables"]]',
                    f"z_index = {z_idx}",
                    'script = ExtResource("2")',
                    f"use_gravity = {str(family == 'platformer').lower()}",
                    f"pushed_switch = {_inum(props.get('activate_pushed_switch_number', '0')) if props.get('activate_pushed_switch', '0') == '1' else 0}",
                    f'gc_id = "{obj_id}"',
                    *common_props,
                ])
            elif is_enemy and has_tex:
                family = _obj_family(obj_type)
                mode = "shooter" if family == "shooter" else (
                    "rpg" if family in ("rpg", "topview") else "platformer"
                )
                espd = _fnum(props.get("move_speed", "3")) * MOVE_SPEED_SCALE
                mdir = _inum(props.get("move_direction", "1"))
                tow = _inum(props.get("move_towards_player", "0"))
                use_grav = family == "platformer" and props.get("gravity", "1") == "1"
                ehp = _inum(_prop(props, "self_health", "health", default="30"))
                infinite = props.get("infinite_health", "0") == "1"
                dmg = _inum(props.get("damage", "10")) if props.get("collide_player", "1") == "1" else 0
                can_shoot = props.get("can_shoot", "0") == "1" or props.get("has_gun", "0") == "1"
                eshoot_dir = _inum(props.get("shooting_direction", "0"))
                ebspd = _fnum(_prop(props, "bullet_speed", default="15")) * BULLET_SPEED_SCALE or 300.0
                ebdmg = _inum(props.get("bullet_damage", "10"))
                embullets = max(1, _inum(props.get("bullet_range", "1")))
                eblife = _fnum(_prop(props, "bullet_lifetime", default="2")) or 2.0
                # Частота выстрелов: 2 в оригинале -> примерно 1 выстрел в 0.5 сек.
                freq = _fnum(props.get("bullet_frequency", "0"))
                interval = 1.0 / freq if freq > 0 else 1.2
                move_shape = _inum(props.get("move_shape", "0"))
                lines.append(
                    '[ext_resource type="Script" path="res://scripts/enemy.gd" id="2"]'
                )
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({max(8, br - bl)}, {max(8, bb - bt)})",
                ])
                enemy_extra = []
                eb_shape = (10.0, 8.0)
                bullet_sid = props.get("bullet_sprite", "-1")
                if bullet_sid in sprite_info:
                    bfn, _, _, _, bbox = sprite_info[bullet_sid]
                    eb_shape = (max(4, bbox[2] - bbox[0]), max(4, bbox[3] - bbox[1]))
                    # ext_resource должны идти до sub_resource в .tscn
                    lines.insert(4, f'[ext_resource type="Texture2D" path="res://sprites/{bfn}" id="4"]')
                    lines[0] = lines[0].replace("load_steps=5", "load_steps=6").replace("load_steps=3", "load_steps=4")
                    enemy_extra.append('bullet_tex = ExtResource("4")')
                enemy_extra.append(f'bullet_shape = Vector2({eb_shape[0]}, {eb_shape[1]})')
                enemy_extra.append(f'gc_id = "{obj_id}"')
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="CharacterBody2D" groups=["enemies"]]',
                    f"z_index = {z_idx + 2}",
                    'script = ExtResource("2")',
                    f'mode = "{mode}"',
                    *enemy_extra,
                    f"speed = {espd}",
                    f"max_hp = {ehp}",
                    f"hp = {ehp}",
                    f"infinite_health = {str(infinite).lower()}",
                    f"contact_damage = {dmg}",
                    f"use_gravity = {str(use_grav).lower()}",
                    f"move_dir_mode = {mdir}",
                    f"move_shape = {move_shape}",
                    f"towards_player = {tow}",
                    f"random_direction = {_inum(props.get('random_direction', '0'))}",
                    f"ignore_objects = {str(props.get('ignore_objects', '0') == '1').lower()}",
                    f"show_health_bar = {str(props.get('health_bar', '0') == '1').lower()}",
                    f"health_bar_width = {_inum(props.get('health_bar_width', '40'))}",
                    f"health_bar_height = {max(3, _inum(props.get('health_bar_height', '6')))}",
                    f"health_bar_color = {get_gc_color(props.get('health_bar_color', '108'), 'Color(0.9, 0.2, 0.2, 1)')}",
                    f"health_bar_offset = {_fnum(props.get('health_bar_position', '-20')) / COORD_SCALE_FALLBACK}",
                    f"turn_to_player = {_inum(props.get('turn_to_player', '0'))}",
                    f"boss = {str(props.get('boss', '0') == '1').lower()}",
                    f"can_shoot = {str(can_shoot).lower()}",
                    f"shoot_dir = {eshoot_dir}",
                    f"bullet_speed = {ebspd}",
                    f"bullet_damage = {ebdmg}",
                    f"bullet_max_count = {embullets}",
                    f"bullet_lifetime = {eblife}",
                    f"shoot_interval = {round(interval, 3)}",
                    f"death_switch = {_inum(props.get('activate_dead_switch_number', '0')) if props.get('activate_dead_switch', '0') == '1' else 0}",
                    *common_props,
                ])
            else:
                grp = ' groups=["teleport_end"]' if obj_role == "TELEPORT END" else ""
                lines.append(
                    '[ext_resource type="Script" path="res://scripts/interactive.gd" id="2"]'
                )
                iextra = []
                asid = props.get("activated_sprite", "-1")
                if asid in sprite_info and asid != spr_id:
                    afn = sprite_info[asid][0]
                    lines.insert(3, f'[ext_resource type="Texture2D" path="res://sprites/{afn}" id="4"]')
                    iextra.append('activated_tex = ExtResource("4")')
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({max(8, br - bl)}, {max(8, bb - bt)})",
                ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="Area2D"{grp}]',
                    f"z_index = {z_idx}",
                    'script = ExtResource("2")',
                    f'role = "{obj_role}"',
                    *common_props,
                    f'switch_num = {_inum(props.get("number", "0"))}',
                    f'switch_mode = {_inum(props.get("switch_mode", "2"))}',
                    f'by_bullet = {"true" if props.get("activate_by_bullet", "0") == "1" else "false"}',
                    f'by_melee = {"true" if props.get("activate_by_melee", "0") == "1" else "false"}',
                    f'ignore_player = {"true" if props.get("switch_ignore_player", "0") == "1" else "false"}',
                    f'once = {"true" if props.get("activated_once_play", "0") == "1" else "false"}',
                    f'action_score = {_inum(props.get("action_score", "0"))}',
                    f'popup_index = {_inum(props.get("popup_index", "0"))}',
                    f'grant_gun = {"true" if props.get("player_can_shoot", "0") == "1" else "false"}',
                    f'action_health = {_inum(props.get("action_health", "0"))}',
                    f'damage = {_inum(props.get("damage", "25"))}',
                    f'timer_id = {_inum(props.get("action_timer_id", "0"))}',
                    f'timer_secs = {_fnum(props.get("action_timer_seconds", "0"))}',
                    f'need_score = {_inum(props.get("check_level_score_value", "0")) if props.get("check_level_score", "0") == "1" else 0}',
                    f'need_cleared = "{props.get("check_type_cleared_value", "") if props.get("check_type_cleared", "0") == "1" else ""}"',
                    f'gc_id = "{obj_id}"',
                    *iextra,
                ])

            if has_tex:
                lines.extend([
                    '[node name="Sprite2D" type="Sprite2D" parent="."]',
                    'texture = ExtResource("1")',
                    "centered = false",
                    f"modulate = Color(1, 1, 1, {max(0.0, min(1.0, _fnum(props.get('alpha', '100')) / 100.0)):.3f})",
                    f"hframes = {frames}",
                    'script = ExtResource("3")',
                    f"fps = {fps}",
                ])

            lines.extend([
                '[node name="CollisionShape2D" type="CollisionShape2D" parent="."]',
                f"position = Vector2({shape_cx}, {shape_cy})",
                'shape = SubResource("sh")',
            ])

            # Пересчитываем load_steps по факту: ресурсов может быть разное число.
            n_res = sum(1 for l in lines if l.startswith(("[ext_resource", "[sub_resource")))
            lines[0] = f"[gd_scene load_steps={n_res + 1} format=3]"
            tscn = "\n".join(lines) + "\n"

        with open(
            os.path.join(out_dir, f"Obj_{obj_id}.tscn"),
            "w",
            encoding="utf-8",
        ) as out:
            out.write(tscn)
        created_objs.add(obj_id)

    return created_objs, fixed_hud