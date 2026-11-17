import os, glob

INPUT_DIR = os.path.join("workspace", "input_game")
RAW_DIR = os.path.join("workspace", "unpacked_files")
SHEETS_DIR = os.path.join("workspace", "sprite_sheets")
GODOT_DIR = os.path.join("workspace", "GodotProject")

PALETTE_RGB = [
    (r * 51 / 255.0, g * 51 / 255.0, b * 51 / 255.0)
    for r in range(6) for g in range(6) for b in range(6)
] + [((i * 255 / 39.0) / 255.0,) * 3 for i in range(40)]

PALETTE_RGBA = [
    (r * 51, g * 51, b * 51, 255)
    for r in range(6) for g in range(6) for b in range(6)
] + [(int(i * 255 / 38), int(i * 255 / 38), int(i * 255 / 38), 255) for i in range(39)] + [(0, 0, 0, 0)]

def get_gc_color(idx_str: str, default_col: str = "Color(1, 1, 1, 1)") -> str:
    try:
        idx = max(0, min(255, int(idx_str)))
        r, g, b = PALETTE_RGB[idx]
        return f"Color({r:.3f}, {g:.3f}, {b:.3f}, 1)"
    except ValueError:
        return default_col

def detect_game_info() -> tuple[str, str]:
    pck_files = glob.glob(os.path.join(INPUT_DIR, "*.pck"))
    if not pck_files:
        raise FileNotFoundError(f"Положите файлы игры (.pck и .gcg) в папку {INPUT_DIR}")
    pck_path = pck_files[0]
    gcg_path = pck_path.replace(".pck", ".gcg")
    game_name = "Exported GameCreator Project"
    if os.path.exists(gcg_path):
        with open(gcg_path, "rb") as f:
            first_line = f.read().decode("utf-8", errors="ignore").splitlines()
            if first_line and first_line[0].strip():
                game_name = first_line[0].strip().replace('"', "'")
    return pck_path, game_name

def parse_obj_file(path: str) -> tuple[str, str, dict]:
    with open(path, "rb") as f:
        lines = [l.strip() for l in f.read().decode("utf-8", errors="ignore").splitlines() if l.strip()]
    if not lines:
        return "", "", {}
    obj_type = lines[1].lower() if len(lines) > 1 else ""
    obj_role = lines[2].upper() if len(lines) > 2 else ""
    props = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
    return obj_type, obj_role, props
