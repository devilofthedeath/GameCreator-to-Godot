import os, glob
from converter.config import RAW_DIR, parse_obj_file

# 1. Ищем ключ удара в прыжке у платформера
for obj in glob.glob(os.path.join(RAW_DIR, "*.obj")):
    t, r, props = parse_obj_file(obj)
    if "platformer_player" in t:
        print("=== 1. Спрайты и атаки платформера ===")
        print({k: v for k, v in props.items() if "sprite" in k or "melee" in k or "gun" in k})
        break

# 2. Смотрим все строки вокруг 1 + 65*6 в .lei (почему не прочитались остальные слои)
lei = os.path.join(RAW_DIR, "20198121612111212.lei")
with open(lei, "rb") as f:
    lines = [l.strip() for l in f.read().decode("utf-8", errors="ignore").splitlines() if l.strip()]
pos = 1 + int(lines[1]) * 6
print(f"\n=== 2. Строки LEI после первого блока (с позиции {pos} из {len(lines)}) ===")
print(lines[pos:pos+25])

# 3. Проверяем .gcg и названия всех уровней (.led) на предмет Victory / Lose
gcg = next(iter(glob.glob("workspace/input_game/*.gcg")), None)
if gcg:
    with open(gcg, "rb") as f:
        print("\n=== 3. Содержимое GCG ===")
        print(f.read().decode("utf-8", errors="ignore").splitlines())
