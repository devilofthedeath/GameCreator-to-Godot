import glob
import os

from converter.config import RAW_DIR, GODOT_DIR, get_gc_color, parse_obj_file


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
        tid = int(props.get("timer_id", "1"))
        tsec = float(props.get("timer_seconds", "10"))
        tp1 = int(props.get("timer_param1", "0"))
        tsong = props.get("timer_song", "")
        has_snd = tsong in audio_files
        lines = [
            f"[gd_scene load_steps={3 if has_snd else 2} format=3]",
            '[ext_resource type="Script" path="res://scripts/hud_widgets.gd" id="1"]',
        ]
        if has_snd:
            lines.append(
                f'[ext_resource type="AudioStream" path="res://audio/{audio_files[tsong]}" id="2"]'
            )
        lines.extend([
            f'[node name="Obj_{obj_id}" type="Control"]',
            f"visible = {s_vis}",
            'script = ExtResource("1")',
            'widget_type = "TIMER"',
            f"timer_id = {tid}",
            f"default_seconds = {tsec}",
            f"timer_param1 = {tp1}",
        ])
        if has_snd:
            lines.append('timer_song_stream = ExtResource("2")')
        lines.extend([
            '[node name="Lbl" type="Label" parent="."]',
            f"theme_override_colors/font_color = {tcol}",
            f'text = "{int(tsec)}"',
        ])
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
    fname, frames, fw, fh = sprite_info[props["main_sprite"]]
    cx, cy = fw / 2.0, fh / 2.0

    mode = "shooter" if "scrollershooter" in obj_type else (
        "rpg" if ("rpg" in obj_type or "topview" in obj_type) else "platformer"
    )
    has_gun = "true" if props.get("has_gun", "0") == "1" else "false"
    spd = float(props.get("move_speed", "10")) * 30.0
    jmp = -float(props.get("jump_strength", "12")) * 43.0
    mdmg = int(props.get("melee_damage", "10"))

    ex_res = []
    ex_pr = ['tex_idle = ExtResource("1")', f"frames_idle = {frames}"]
    r_i = 4

    anim_map = [
        (["move_sprite", "move_leftright_sprite"], "tex_move", "frames_move"),
        (["jump_sprite"], "tex_jump", "frames_jump"),
        (["shoot_sprite", "shoot_leftright_sprite"], "tex_shoot", "frames_shoot"),
        (["melee_sprite", "melee_leftright_sprite"], "tex_melee", "frames_melee"),
        (["bullet_sprite", "bullet_sprite_lv1"], "tex_bullet", None),
    ]
    for pks, ptex, pfr in anim_map:
        for pk in pks:
            sid = props.get(pk, "-1")
            if sid in sprite_info:
                fn, fc, _, _ = sprite_info[sid]
                ex_res.append(
                    f'[ext_resource type="Texture2D" path="res://sprites/{fn}" id="{r_i}"]'
                )
                ex_pr.append(f'{ptex} = ExtResource("{r_i}")')
                if pfr:
                    ex_pr.append(f"{pfr} = {fc}")
                r_i += 1
                break

    lines = [
        f"[gd_scene load_steps={r_i} format=3]",
        f'[ext_resource type="Texture2D" path="res://sprites/{fname}" id="1"]',
        '[ext_resource type="Script" path="res://scripts/player_master.gd" id="2"]',
        '[ext_resource type="Script" path="res://scripts/anim_sprite.gd" id="3"]',
        *ex_res,
        '[sub_resource type="RectangleShape2D" id="sh"]',
        f"size = Vector2({max(8, fw - 4)}, {max(8, fh - 2)})",
        f'[node name="Obj_{obj_id}" type="CharacterBody2D"]',
        f"z_index = {z_idx + 5}",
        'script = ExtResource("2")',
        f'mode = "{mode}"',
        f"speed = {spd}",
        f"jump_force = {jmp}",
        f"has_gun = {has_gun}",
        f"melee_damage = {mdmg}",
        *ex_pr,
        '[node name="Sprite2D" type="Sprite2D" parent="."]',
        'texture = ExtResource("1")',
        "centered = false",
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
        if not props or obj_role == "POPUP":
            continue

        obj_id = os.path.basename(obj_path).replace(".obj", "")
        if props.get("fixed", "0") == "1":
            fixed_hud.add(obj_id)

        spr_id = props.get("main_sprite", "-1")
        z_idx = int(props.get("depth", "0"))
        fps = float(props.get("animation_speed", "10"))
        s_vis = "true" if props.get("visible", "1") == "1" else "false"
        s_act = "true" if props.get("active", "1") == "1" else "false"
        l_num = int(props.get("listener", "0"))
        v_sw = int(props.get("visible_when_switched", "0"))
        a_sw = int(props.get("activate_when_switched", "0"))
        r_sw = int(props.get("remove_when_switched", "0"))

        is_player = obj_role == "PLAYER" or obj_type.endswith("_player")
        is_solid = (
            obj_role in ["BLOCK", "DESTROYABLE BLOCK", "PUSHABLE OBJECT"]
            or "_block" in obj_type
        )
        is_enemy = obj_role in ["ENEMY", "MONSTER"]
        has_tex = spr_id in sprite_info

        if obj_role in ["HEALTH", "SCORE", "TIMER", "TEXT"]:
            tscn = _build_hud_tscn(obj_id, obj_role, props, audio_files, s_vis, z_idx)
        elif is_player and has_tex:
            tscn = _build_player_tscn(obj_id, obj_type, props, sprite_info, z_idx, fps)
        else:
            fname, frames, fw, fh = sprite_info[spr_id] if has_tex else ("", 1, 40, 40)
            cx, cy = fw / 2.0, fh / 2.0
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
                    f"size = Vector2({fw}, {fh})",
                ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="StaticBody2D"]',
                    f"z_index = {z_idx}",
                    'script = ExtResource("2")',
                    *common_props,
                ])
            elif is_enemy and has_tex:
                lines.append(
                    '[ext_resource type="Script" path="res://scripts/enemy.gd" id="2"]'
                )
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({fw}, {fh})",
                ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="CharacterBody2D" groups=["enemies"]]',
                    f"z_index = {z_idx + 2}",
                    'script = ExtResource("2")',
                    *common_props,
                ])
            else:
                grp = ' groups=["teleport_end"]' if obj_role == "TELEPORT END" else ""
                lines.append(
                    '[ext_resource type="Script" path="res://scripts/interactive.gd" id="2"]'
                )
                lines.extend([
                    '[sub_resource type="RectangleShape2D" id="sh"]',
                    f"size = Vector2({fw}, {fh})",
                ])
                lines.extend([
                    f'[node name="Obj_{obj_id}" type="Area2D"{grp}]',
                    f"z_index = {z_idx}",
                    'script = ExtResource("2")',
                    f'role = "{obj_role}"',
                    *common_props,
                    f'switch_num = {int(props.get("number", "0"))}',
                    f'switch_mode = {int(props.get("switch_mode", "2"))}',
                    f'by_bullet = {"true" if props.get("activate_by_bullet", "0") == "1" else "false"}',
                    f'by_melee = {"true" if props.get("activate_by_melee", "0") == "1" else "false"}',
                    f'ignore_player = {"true" if props.get("switch_ignore_player", "0") == "1" else "false"}',
                    f'action_score = {int(props.get("action_score", "0"))}',
                    f'popup_index = {int(props.get("popup_index", "0"))}',
                    f'grant_gun = {"true" if props.get("player_can_shoot", "0") == "1" else "false"}',
                    f'timer_id = {int(props.get("action_timer_id", "0"))}',
                    f'timer_secs = {float(props.get("action_timer_seconds", "0"))}',
                ])

            if has_tex:
                lines.extend([
                    '[node name="Sprite2D" type="Sprite2D" parent="."]',
                    'texture = ExtResource("1")',
                    "centered = false",
                    f"hframes = {frames}",
                    'script = ExtResource("3")',
                    f"fps = {fps}",
                ])

            lines.extend([
                '[node name="CollisionShape2D" type="CollisionShape2D" parent="."]',
                f"position = Vector2({cx}, {cy})",
                'shape = SubResource("sh")',
            ])

            tscn = "\n".join(lines) + "\n"

        with open(
            os.path.join(out_dir, f"Obj_{obj_id}.tscn"),
            "w",
            encoding="utf-8",
        ) as out:
            out.write(tscn)
        created_objs.add(obj_id)

    return created_objs, fixed_hud