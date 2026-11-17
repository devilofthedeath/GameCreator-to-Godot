import os, shutil
from converter.config import RAW_DIR, SHEETS_DIR, GODOT_DIR, detect_game_info
from converter.unpacker import unpack_pck_and_build_sheets
from converter.assets import export_audio, export_sprites, collect_popups
from converter.gd_templates import write_gd_scripts
from converter.object_builder import build_objects
from converter.level_builder import build_levels

def main():
    pck_path, game_name = detect_game_info()
    print(f"Найден проект: '{game_name}' ({os.path.basename(pck_path)})")

    for folder in [RAW_DIR, SHEETS_DIR, GODOT_DIR]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    for sub in ["sprites", "objects", "levels", "scripts", "audio"]:
        os.makedirs(os.path.join(GODOT_DIR, sub), exist_ok=True)

    print("1/5 Распаковка .pck и склейка спрайт-шитов...")
    sheets_cnt = unpack_pck_and_build_sheets(pck_path)

    print("2/5 Конвертация звуков (.sng -> .wav) и сбор диалогов...")
    audio_files = export_audio()
    sprite_info = export_sprites()
    popups = collect_popups()

    print("3/5 Генерация GDScript-логики...")
    write_gd_scripts(popups)

    print("4/5 Сборка объектов, коллизий и HUD...")
    created_objs, fixed_hud = build_objects(sprite_info, audio_files)

    print("5/5 Генерация уровней и project.godot...")
    first_lvl = build_levels(created_objs, fixed_hud, audio_files)

    with open(os.path.join(GODOT_DIR, "project.godot"), "w", encoding="utf-8") as f:
        f.write(
            f'config_version=5\n[application]\nconfig/name="{game_name}"\n'
            f'run/main_scene="{first_lvl}"\nconfig/features=PackedStringArray("4.7")\n'
            f'[autoload]\nGameState="*res://scripts/GameState.gd"\n'
            f'[rendering]\ntextures/canvas_textures/default_texture_filter=0\n'
        )
    print(f"\nУспех! Спрайт-шитов: {sheets_cnt} | Объектов: {len(created_objs)} | Диалогов: {len(popups)}")
    print(f"Откройте в Godot 4.7: {os.path.abspath(os.path.join(GODOT_DIR, 'project.godot'))}")

if __name__ == "__main__":
    main()
