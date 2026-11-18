import os, glob, shutil
from PIL import Image
from converter.config import RAW_DIR, SHEETS_DIR, GODOT_DIR, parse_obj_file
from converter.synth import sng_bytes_to_wav

def export_audio() -> dict[str, str]:
    audio_map = {}
    out_dir = os.path.join(GODOT_DIR, "audio")
    for sng_path in glob.glob(os.path.join(RAW_DIR, "*.sng")):
        sng_id = os.path.basename(sng_path).replace(".sng", "")
        wav_name = f"snd_{sng_id}.wav"
        with open(sng_path, "rb") as f:
            raw_bytes = f.read()
        sng_bytes_to_wav(raw_bytes, os.path.join(out_dir, wav_name))
        audio_map[sng_id] = wav_name
    return audio_map

def export_sprites() -> dict[str, tuple]:
    """id -> (имя файла, кадров, w, h, bbox коллизии).

    Game Creator считает коллизию по непрозрачным пикселям спрайта, а не по
    размеру кадра, поэтому bbox берём из альфа-канала (объединение кадров).
    """
    sprite_map = {}
    out_dir = os.path.join(GODOT_DIR, "sprites")
    for path in glob.glob(os.path.join(SHEETS_DIR, "*.png")):
        fname = os.path.basename(path)
        shutil.copy2(path, os.path.join(out_dir, fname))
        parts = fname.replace(".png", "").split("_")
        if len(parts) != 2 or not parts[-1].endswith("f"):
            continue
        spr_id, frames_str = parts
        frames = max(1, int(frames_str[:-1]))
        with Image.open(path) as im:
            total_w, total_h = im.size
            fw = max(1, total_w // frames)
            alpha = im.getchannel("A").copy()
        l, t, r, b = 0, 0, fw, total_h
        found = False
        for i in range(frames):
            fb = alpha.crop((i * fw, 0, (i + 1) * fw, total_h)).getbbox()
            if fb:
                if not found:
                    l, t, r, b = fb
                    found = True
                else:
                    l, t = min(l, fb[0]), min(t, fb[1])
                    r, b = max(r, fb[2]), max(b, fb[3])
        if not found:
            l, t, r, b = 0, 0, fw, total_h

        # В .spr есть ЯВНАЯ настройка коллизии:
        #   [0]=id [1]=w [2]=h [3]=w/2 [4]=h/2 [5]=флаг
        #   [6..9]=прямоугольник [10]=число кадров [11..]=id кадров
        # При флаге 1 координаты идут в порядке (left=n2, top=n0, right=n3, bottom=n1).
        spr_cfg = os.path.join(RAW_DIR, f"{spr_id}.spr")
        if os.path.exists(spr_cfg):
            sl = [x.strip() for x in open(spr_cfg, "rb").read().decode("utf-8", "ignore").splitlines() if x.strip()]
            if len(sl) >= 10 and sl[5] == "1":
                try:
                    n = [int(x) for x in sl[6:10]]
                    cl, ct, cr, cb = n[2], n[0], n[3], n[1]
                    if 0 <= cl < cr <= fw and 0 <= ct < cb <= total_h:
                        l, t, r, b = cl, ct, cr, cb
                except ValueError:
                    pass
        sprite_map[spr_id] = (fname, frames, fw, total_h, (l, t, r, b))
    return sprite_map

def collect_popups() -> dict[int, list[str]]:
    popups = {}
    for obj_path in glob.glob(os.path.join(RAW_DIR, "*.obj")):
        _, role, props = parse_obj_file(obj_path)
        if role == "POPUP":
            idx = int(props.get("index", "0"))
            lines = [props.get(f"text{n}", "").strip() for n in range(1, 11)]
            clean_lines = [t for t in lines if t]
            if idx > 0 and clean_lines:
                popups[idx] = clean_lines
    return popups
