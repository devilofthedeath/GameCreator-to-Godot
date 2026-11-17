import os, glob
from converter.config import RAW_DIR, GODOT_DIR, get_gc_color

def build_levels(created_objs: set, fixed_hud: set, audio_files: dict) -> str:
    first_lvl = ""
    out_dir = os.path.join(GODOT_DIR, "levels")

    def resolve_id(ref: str):
        if ref in created_objs:
            return ref
        for c in range(1, 4):
            if ref[c:] in created_objs:
                return ref[c:]
        return None

    for led_path in sorted(glob.glob(os.path.join(RAW_DIR, "*.led"))):
        lvl_id = os.path.basename(led_path).replace(".led", "")
        lei_path = os.path.join(RAW_DIR, f"{lvl_id}.lei")
        if not os.path.exists(lei_path):
            continue

        with open(led_path, "rb") as f:
            led_lines = [l.strip() for l in f.read().decode("utf-8", errors="ignore").splitlines() if l.strip()]

        lprops = {}
        lvl_title = lvl_id
        for line in led_lines:
            if line.startswith("LEVEL "):
                lvl_title = line.replace(" ", "_")
            elif "=" in line:
                k, v = line.split("=", 1)
                lprops[k.strip()] = v.strip()

        song_id = lprops.get("song", "")
        use_grad = lprops.get("gradient_color", "0") == "1"
        c_bg = get_gc_color(lprops.get("background_color", "0"))
        c_g1 = get_gc_color(lprops.get("gradient_color_1", "0"))
        c_g2 = get_gc_color(lprops.get("gradient_color_2", "51"))
        g_type = lprops.get("gradient_type", "3")

        with open(lei_path, "rb") as f:
            lei_lines = [l.strip() for l in f.read().decode("utf-8", errors="ignore").splitlines() if l.strip()]

        blocks, pos = [], 0
        while pos < len(lei_lines) and lei_lines[pos].isdigit():
            cnt = int(lei_lines[pos])
            pos += 1
            items = []
            for _ in range(cnt):
                if pos + 5 >= len(lei_lines):
                    break
                ref, xv, yv, _, sxv, syv = lei_lines[pos:pos + 6]
                pos += 6
                cid = resolve_id(ref)
                if cid:
                    items.append((cid, float(xv), float(yv), float(sxv) / 100.0, float(syv) / 100.0))
            blocks.append(items)

        it = iter(blocks)
        raw_main = next(it, [])
        bg_items = next(it, [])

        world_items = [item for item in raw_main if item[0] not in fixed_hud]
        hud_items = [item for item in raw_main if item[0] in fixed_hud]

        refs = sorted({oid for oid, *_ in (world_items + bg_items + hud_items)})
        ext_l, rmap, ri = [], {}, 1
        for oid in refs:
            rmap[oid] = f"{ri}_o"
            ext_l.append(f'[ext_resource type="PackedScene" path="res://objects/Obj_{oid}.tscn" id="{ri}_o"]')
            ri += 1

        has_song = song_id in audio_files
        bgm_id = ""
        if has_song:
            bgm_id = f"{ri}_bgm"
            ext_l.append(f'[ext_resource type="AudioStream" path="res://audio/{audio_files[song_id]}" id="{bgm_id}"]')
            ri += 1

        sub_b = []
        if use_grad:
            fto = "Vector2(1, 0)" if g_type == "1" else ("Vector2(1, 1)" if g_type == "2" else "Vector2(0, 1)")
            sub_b = [
                '[sub_resource type="Gradient" id="gb"]',
                f"colors = PackedColorArray({c_g1[6:-1]}, {c_g2[6:-1]})",
                '[sub_resource type="GradientTexture2D" id="gtb"]',
                'gradient = SubResource("gb")',
                f"fill_to = {fto}",
            ]

        nl = [f'[node name="{lvl_title}" type="Node2D"]', '[node name="Sky" type="CanvasLayer" parent="."]', "layer = -2"]
        if use_grad:
            nl.extend(['[node name="Bg" type="TextureRect" parent="Sky"]', "anchors_preset = 15", "anchor_right = 1.0", "anchor_bottom = 1.0", 'texture = SubResource("gtb")'])
        else:
            nl.extend(['[node name="Bg" type="ColorRect" parent="Sky"]', "anchors_preset = 15", "anchor_right = 1.0", "anchor_bottom = 1.0", f"color = {c_bg}"])

        if bg_items:
            nl.extend(['[node name="FixedBG" type="CanvasLayer" parent="."]', "layer = -1"])
            for i, (oid, x, y, sx, sy) in enumerate(bg_items):
                nl.extend([f'[node name="Bg_{i}" parent="FixedBG" instance=ExtResource("{rmap[oid]}")]', f"position = Vector2({x}, {y})", f"scale = Vector2({sx}, {sy})"])

        for i, (oid, x, y, sx, sy) in enumerate(world_items):
            nl.extend([f'[node name="W_{i}" parent="." instance=ExtResource("{rmap[oid]}")]', f"position = Vector2({x}, {y})", f"scale = Vector2({sx}, {sy})"])

        if hud_items:
            nl.extend(['[node name="HUD" type="CanvasLayer" parent="."]', "layer = 10"])
            for i, (oid, x, y, sx, sy) in enumerate(hud_items):
                nl.extend([f'[node name="Hud_{i}" parent="HUD" instance=ExtResource("{rmap[oid]}")]', f"position = Vector2({x}, {y})", f"scale = Vector2({sx}, {sy})"])

        if has_song:
            nl.extend(['[node name="BGM" type="AudioStreamPlayer" parent="."]', f'stream = ExtResource("{bgm_id}")', "autoplay = true"])

        sfile = f"{lvl_title}_{lvl_id}.tscn"
        full_lines = [f"[gd_scene load_steps={ri + 2} format=3]", *ext_l, *sub_b, *nl]
        with open(os.path.join(out_dir, sfile), "w", encoding="utf-8") as out:
            out.write("\n".join(full_lines) + "\n")

        if "LEVEL_2" in lvl_title or not first_lvl:
            first_lvl = f"res://levels/{sfile}"

    return first_lvl