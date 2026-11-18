import os, glob, math, re
from converter.config import RAW_DIR, SHEETS_DIR, GODOT_DIR, get_gc_color
from converter.settings import COORD_SCALE, SCREEN_W, SCREEN_H


def _object_half_sizes(created_objs: set) -> dict[str, tuple[float, float]]:
    """Половина размера кадра спрайта в пикселях — нужна, чтобы перевести
    координату центра объекта из .lei в координату левого верхнего угла."""
    out = {}
    for obj_path in glob.glob(os.path.join(RAW_DIR, "*.obj")):
        oid = os.path.basename(obj_path)[:-4]
        if oid not in created_objs:
            continue
        lines = [l.strip() for l in open(obj_path, "rb").read().decode("utf-8", "ignore").splitlines() if l.strip()]
        spr_id = None
        for line in lines:
            if line.startswith("main_sprite="):
                spr_id = line.split("=", 1)[1]
                break
        if not spr_id or spr_id == "-1":
            continue
        spr_path = os.path.join(RAW_DIR, f"{spr_id}.spr")
        if not os.path.exists(spr_path):
            continue
        sl = [l.strip() for l in open(spr_path, "rb").read().decode("utf-8", "ignore").splitlines() if l.strip()]
        if len(sl) >= 3 and sl[1].isdigit() and sl[2].isdigit():
            out[oid] = (int(sl[1]) / 2.0, int(sl[2]) / 2.0)
    return out


def _parse_lei_items(lei_path: str, created_objs: set, half_sizes: dict | None = None) -> list[tuple]:
    if not os.path.exists(lei_path):
        return []
    with open(lei_path, "rb") as f:
        lines = [l.strip() for l in f.read().decode("utf-8", "ignore").splitlines() if l.strip()]
    if not lines or not lines[0].isdigit():
        return []

    def resolve_id(ref: str):
        if ref in created_objs:
            return ref
        for c in range(1, 4):
            if ref[c:] in created_objs:
                return ref[c:]
        return None

    items = []
    pos = 1
    while pos + 5 < len(lines):
        ref, xv, yv, rotv, sxv, syv = lines[pos:pos + 6]
        pos += 6
        cid = resolve_id(ref)
        if not cid:
            continue
        try:
            rot = float(rotv)
        except ValueError:
            rot = 0.0
        # Масштаб задан в процентах (100 -> 1.0). НЕ округляем: невидимые
        # стены часто имеют 70 / 95 / 209.28 / 305 и т.п.
        try:
            sx = float(sxv) / 100.0
            sy = float(syv) / 100.0
        except ValueError:
            sx, sy = 1.0, 1.0
        px, py = float(xv) / COORD_SCALE, float(yv) / COORD_SCALE
        # В .lei координата — центр объекта. Godot wants top-left of the sprite.
        hw, hh = (half_sizes or {}).get(cid, (0.0, 0.0))
        items.append((cid, px - hw * sx, py - hh * sy, sx, sy, rot))
    return items


def _level_number(title: str, props: dict) -> int:
    m = re.search(r"LEVEL\s+(\d+)", title, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"LEVEL\s+(\d+)", props.get("level_name", ""), re.I)
    return int(m.group(1)) if m else 10 ** 6


def _level_is_victory(props: dict) -> bool:
    n = props.get("level_name", "").lower()
    return "victory" in n or "win" in n or "побед" in n


def _level_is_lose(props: dict) -> bool:
    n = props.get("level_name", "").lower()
    return "lose" in n or "game over" in n or "over" in n or "пораж" in n


def _sheet_for(spr_id: str) -> str | None:
    hits = glob.glob(os.path.join(SHEETS_DIR, f"{spr_id}_*.png"))
    return os.path.basename(hits[0]) if hits else None


def _background_nodes(lprops: dict, ri: int) -> tuple[list[str], list[str], list[str]]:
    """Возвращает (ext_resources, sub_resources, nodes) для фона уровня."""
    grad = lprops.get("gradient_color", "0") == "1"
    pattern = lprops.get("pattern", "0") == "1"
    pspr = lprops.get("pattern_sprite", "-1")
    fixed = lprops.get("background_fixed", "0") == "1"
    alpha = max(0.0, min(1.0, float(lprops.get("background_alpha", "100")) / 100.0))
    w = max(1, int(float(lprops.get("width", "1")))) * SCREEN_W
    h = max(1, int(float(lprops.get("height", "1")))) * SCREEN_H

    ext, subs, nodes = [], [], []
    # Фон всегда лежит в отдельном CanvasLayer с отрицательным layer —
    # тогда он гарантированно позади всех игровых объектов, даже с z_index<0.
    ext.append('[ext_resource type="Script" path="res://scripts/bg_scroll.gd" id="bgscroll"]')
    ri += 1
    nodes.extend([
        '[node name="Sky" type="CanvasLayer" parent="."]',
        "layer = -2",
        '[node name="Parallax" type="Node2D" parent="Sky"]',
        'script = ExtResource("bgscroll")',
        f"scroll_factor = {0.0 if fixed else 1.0}",
    ])

    pat_file = _sheet_for(pspr) if pattern and pspr != "-1" else None
    if pat_file:
        ext.append(f'[ext_resource type="Texture2D" path="res://sprites/{pat_file}" id="{ri}_pat"]')
        ri += 1
        nodes.extend([
            '[node name="Bg" type="TextureRect" parent="Sky/Parallax"]',
            f"position = Vector2(0, 0)",
            f"size = Vector2({w}, {h})",
            f"texture = ExtResource(\"{ri - 1}_pat\")",
            "stretch_mode = 1",  # STRETCH_TILE
            f"modulate = Color(1, 1, 1, {alpha:.3f})",
        ])
    elif grad:
        c1 = get_gc_color(lprops.get("gradient_color_1", "0"), alpha=alpha)
        c2 = get_gc_color(lprops.get("gradient_color_2", "51"), alpha=alpha)
        g_type = lprops.get("gradient_type", "3")
        fto = "Vector2(1, 0)" if g_type == "1" else ("Vector2(1, 1)" if g_type == "2" else "Vector2(0, 1)")
        subs.extend([
            '[sub_resource type="Gradient" id="gb"]',
            f"colors = PackedColorArray({c1[6:-1]}, {c2[6:-1]})",
            '[sub_resource type="GradientTexture2D" id="gtb"]',
            'gradient = SubResource("gb")',
            f"fill_to = {fto}",
            f"width = {w}",
            f"height = {h}",
        ])
        nodes.extend([
            '[node name="Bg" type="TextureRect" parent="Sky/Parallax"]',
            f"size = Vector2({w}, {h})",
            'texture = SubResource("gtb")',
            "stretch_mode = 1",
        ])
    else:
        c_bg = get_gc_color(lprops.get("background_color", "0"), alpha=alpha)
        nodes.extend([
            '[node name="Bg" type="ColorRect" parent="Sky/Parallax"]',
            f"size = Vector2({w}, {h})",
            f"color = {c_bg}",
        ])
    return ext, subs, nodes


def build_levels(created_objs: set, hud_widget_objs: set, audio_files: dict) -> tuple[str, dict]:
    out_dir = os.path.join(GODOT_DIR, "levels")
    all_leds = sorted(glob.glob(os.path.join(RAW_DIR, "*.led")))
    half_sizes = _object_half_sizes(created_objs)

    defs = []
    for led_path in all_leds:
        with open(led_path, "rb") as f:
            txt = f.read().decode("utf-8", "ignore")
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        props = {}
        for line in lines:
            if "=" in line:
                k, v = line.split("=", 1)
                props[k.strip()] = v.strip()
        title = next((l for l in lines if l.startswith("LEVEL ")), "")
        defs.append({"path": led_path, "id": os.path.basename(led_path)[:-4],
                     "title": title, "props": props, "gui": props.get("gui_level", "0") == "1"})

    # Общий GUI-уровень: берём только настоящие HUD-виджеты.
    # DESIGN ITEM с depth=1000000 — это тач-кнопки, они в HUD не нужны.
    global_gui_items = []
    for d in defs:
        if d["gui"]:
            gui_ids = set()
            # Собираем ID виджетов из самих .obj файлов.
            for obj_path in glob.glob(os.path.join(RAW_DIR, "*.obj")):
                ol = [l.strip() for l in open(obj_path, "rb").read().decode("utf-8", "ignore").splitlines() if l.strip()]
                if len(ol) < 3:
                    continue
                role = ol[2].upper()
                op = dict(l.split("=", 1) for l in ol if "=" in l)
                if role in ("HEALTH", "SCORE", "TIMER") or (role == "TEXT" and op.get("fixed", "0") == "1"):
                    gui_ids.add(os.path.basename(obj_path)[:-4])
            global_gui_items = [x for x in _parse_lei_items(d["path"].replace(".led", ".lei"), created_objs, half_sizes) if x[0] in gui_ids]
            break

    # Объекты с fixed=1 остаются на одном экране (например, декорации-оверлеи),
    # а не едут вместе с камерой. HUD-виджеты уже обработаны выше.
    fixed_objs = set()
    for obj_path in glob.glob(os.path.join(RAW_DIR, "*.obj")):
        ol = [l.strip() for l in open(obj_path, "rb").read().decode("utf-8", "ignore").splitlines() if l.strip()]
        if len(ol) < 3:
            continue
        role = ol[2].upper()
        op = dict(l.split("=", 1) for l in ol if "=" in l)
        if op.get("fixed") == "1" and role not in ("HEALTH", "SCORE", "TIMER") and "BUTTON" not in role and role != "TEXT":
            fixed_objs.add(os.path.basename(obj_path)[:-4])

    first_lvl = ""
    level_flow = {"order": [], "victory": "", "lose": "", "by_number": {}}
    numbered = []

    for d in defs:
        if d["gui"]:
            continue
        lvl_id, title, lprops = d["id"], d["title"], d["props"]
        sfile = f"{title.replace(' ', '_')}_{lvl_id}.tscn" if title else f"{lvl_id}_{lvl_id}.tscn"
        res_scene_path = f"res://levels/{sfile}"

        special = False
        if _level_is_victory(lprops):
            level_flow["victory"] = res_scene_path
            special = True
        elif _level_is_lose(lprops):
            level_flow["lose"] = res_scene_path
            special = True

        num = _level_number(title, lprops)
        # Сцены GAME OVER / VICTORY всё равно генерируем — иначе переход
        # после смерти ссылается на несуществующий файл.
        if num < 10 ** 6 and not special:
            numbered.append((num, res_scene_path))
        d["scene"] = res_scene_path

        raw_items = _parse_lei_items(d["path"].replace(".led", ".lei"), created_objs, half_sizes)
        # hud_widget_objs — множество ID объектов, а не кортежей размещения.
        world_items = [x for x in raw_items if x[0] not in hud_widget_objs]
        world_fixed = [x for x in world_items if x[0] in fixed_objs]
        world_items = [x for x in world_items if x[0] not in fixed_objs]
        local_hud = [x for x in raw_items if x[0] in hud_widget_objs]
        combined_hud = global_gui_items + local_hud

        refs = sorted({oid for oid, *_ in (world_items + world_fixed + combined_hud)})
        ext_l, rmap, ri = [], {}, 1
        for oid in refs:
            rmap[oid] = f"{ri}_o"
            ext_l.append(f'[ext_resource type="PackedScene" path="res://objects/Obj_{oid}.tscn" id="{ri}_o"]')
            ri += 1

        song_id = lprops.get("song", "-1")
        if song_id in audio_files:
            bgm_id = f"{ri}_bgm"
            ext_l.append(f'[ext_resource type="AudioStream" path="res://audio/{audio_files[song_id]}" id="{bgm_id}"]')
            ri += 1
        else:
            bgm_id = ""

        ext_bg, subs_bg, nodes_bg = _background_nodes(lprops, ri)
        ext_l.extend(ext_bg)
        ri += len(ext_bg)

        nl = [*subs_bg, f'[node name="{title.replace(" ", "_") or lvl_id}" type="Node2D"]', *nodes_bg]
        ext_l.append('[ext_resource type="Script" path="res://scripts/level_bounds.gd" id="bounds"]')
        ri += 1
        nl.extend([
            '[node name="LevelBounds" type="Node" parent="."]',
            'script = ExtResource("bounds")',
            f"level_width = {max(1, int(float(lprops.get('width', '1')))) * SCREEN_W}",
            f"level_height = {max(1, int(float(lprops.get('height', '1')))) * SCREEN_H}",
        ])

        for i, (oid, x, y, sx, sy, rot) in enumerate(world_items):
            node = [f'[node name="W_{i}" parent="." instance=ExtResource("{rmap[oid]}")]', f"position = Vector2({x}, {y})", f"scale = Vector2({sx}, {sy})"]
            if rot:
                node.append(f"rotation = {math.radians(rot)}")
            nl.extend(node)

        if world_fixed:
            nl.extend(['[node name="FixedLayer" type="CanvasLayer" parent="."]', "layer = -1"])
            for i, (oid, x, y, sx, sy, rot) in enumerate(world_fixed):
                nl.extend([f'[node name="F_{i}" parent="FixedLayer" instance=ExtResource("{rmap[oid]}")]', f"position = Vector2({x}, {y})", f"scale = Vector2({sx}, {sy})"])

        if combined_hud:
            nl.extend(['[node name="HUD" type="CanvasLayer" parent="."]', "layer = 10"])
            for i, (oid, x, y, sx, sy, rot) in enumerate(combined_hud):
                nl.extend([f'[node name="Hud_{i}" parent="HUD" instance=ExtResource("{rmap[oid]}")]', f"position = Vector2({x}, {y})", f"scale = Vector2({sx}, {sy})"])

        if bgm_id:
            nl.extend(['[node name="BGM" type="AudioStreamPlayer" parent="."]', f'stream = ExtResource("{bgm_id}")', "autoplay = true"])

        full_lines = [f"[gd_scene load_steps={ri + 2} format=3]", *ext_l, *nl]
        with open(os.path.join(out_dir, sfile), "w", encoding="utf-8") as out:
            out.write("\n".join(full_lines) + "\n")

        if title == "LEVEL 2" or not first_lvl:
            first_lvl = res_scene_path

    # Порядок уровнеЙ — по номеру из названия, а не по имени файла.
    ordered = [path for _, path in sorted(numbered, key=lambda p: p[0])]
    level_flow["order"] = ordered
    level_flow["by_number"] = {num: path for num, path in numbered}
    return first_lvl, level_flow
