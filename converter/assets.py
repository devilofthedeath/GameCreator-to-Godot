import os, glob, shutil, wave
from PIL import Image
from converter.config import RAW_DIR, SHEETS_DIR, GODOT_DIR, parse_obj_file

def export_audio() -> dict[str, str]:
    audio_map = {}
    out_dir = os.path.join(GODOT_DIR, "audio")
    for sng_path in glob.glob(os.path.join(RAW_DIR, "*.sng")):
        sng_id = os.path.basename(sng_path).replace(".sng", "")
        wav_name = f"snd_{sng_id}.wav"
        with open(sng_path, "rb") as f:
            pcm_data = f.read()
        with wave.open(os.path.join(out_dir, wav_name), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(1)
            wf.setframerate(11025)
            wf.writeframes(pcm_data)
        audio_map[sng_id] = wav_name
    return audio_map

def export_sprites() -> dict[str, tuple[str, int, int, int]]:
    sprite_map = {}
    out_dir = os.path.join(GODOT_DIR, "sprites")
    for path in glob.glob(os.path.join(SHEETS_DIR, "*.png")):
        fname = os.path.basename(path)
        shutil.copy2(path, os.path.join(out_dir, fname))
        parts = fname.replace(".png", "").split("_")
        if len(parts) == 2 and parts[-1].endswith("f"):
            spr_id, frames_str = parts
            frames = int(frames_str[:-1])
            with Image.open(path) as im:
                total_w, total_h = im.size
            sprite_map[spr_id] = (fname, frames, max(1, total_w // frames), total_h)
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
