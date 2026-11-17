import os, re, glob, struct
from PIL import Image
from converter.config import RAW_DIR, SHEETS_DIR, PALETTE_RGBA

def unpack_pck_and_build_sheets(pck_path: str) -> int:
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(SHEETS_DIR, exist_ok=True)

    with open(pck_path, "rb") as f:
        data = f.read()

    pattern = re.compile(rb'[\x05-\x40]([a-zA-Z0-9_]+\.[a-zA-Z0-9]{2,4})')
    matches = []
    for m in pattern.finditer(data):
        name_bytes = m.group(1)
        if data[m.start()] == len(name_bytes):
            matches.append((m.start(), m.end(), name_bytes.decode("ascii")))

    for idx, (start_pos, data_start, name) in enumerate(matches):
        next_start = matches[idx + 1][0] - 1 if idx + 1 < len(matches) else len(data)
        raw_block = data[data_start:next_start]
        if len(raw_block) >= 2:
            size_2 = struct.unpack(">H", raw_block[:2])[0]
            if size_2 == len(raw_block) - 2:
                chunk = raw_block[2:]
            elif len(raw_block) >= 4 and struct.unpack(">I", raw_block[:4])[0] == len(raw_block) - 4:
                chunk = raw_block[4:]
            else:
                chunk = raw_block[2:]
        else:
            chunk = raw_block

        with open(os.path.join(RAW_DIR, name), "wb") as out:
            out.write(chunk)

    # Склеиваем кадры (.frm) в горизонтальные спрайт-шиты по конфигам (.spr)
    sheets_count = 0
    for spr_path in glob.glob(os.path.join(RAW_DIR, "*.spr")):
        with open(spr_path, "rb") as f:
            lines = [l.strip() for l in f.read().decode("utf-8", errors="ignore").splitlines() if l.strip()]
        if len(lines) < 4:
            continue
        spr_id, w_str, h_str = lines[:3]
        if not (w_str.isdigit() and h_str.isdigit()):
            continue
        w, h = int(w_str), int(h_str)
        expected = w * h

        frames = []
        for item in lines[3:]:
            frm_path = os.path.join(RAW_DIR, f"{item}.frm")
            if item.isdigit() and len(item) > 8 and os.path.exists(frm_path):
                with open(frm_path, "rb") as ff:
                    buf = ff.read()
                if len(buf) < expected:
                    buf = (b"\xff" * (expected - len(buf))) + buf
                elif len(buf) > expected:
                    buf = buf[-expected:]
                img = Image.new("RGBA", (w, h))
                img.putdata([PALETTE_RGBA[b] for b in buf])
                frames.append(img)

        if frames:
            sheet = Image.new("RGBA", (w * len(frames), h))
            for i, frame in enumerate(frames):
                sheet.paste(frame, (i * w, 0))
            sheet.save(os.path.join(SHEETS_DIR, f"{spr_id}_{len(frames)}f.png"))
            sheets_count += 1

    return sheets_count
