import os, shutil, glob
from converter.config import RAW_DIR, SHEETS_DIR, GODOT_DIR, OVERRIDES_DIR, detect_game_info
from converter.unpacker import unpack_pck_and_build_sheets
from converter.assets import export_audio, export_sprites, collect_popups
from converter.templates.gamestate import write_gamestate
from converter.templates.player import write_player_script
from converter.templates.entities import write_entity_scripts
from converter.templates.ui import write_ui_script
from converter.dialogue import write_dialogues
from converter.object_builder import build_objects
from converter.level_builder import build_levels

def main():
    pck_path, game_name = detect_game_info()
    print(f"Найден проект: '{game_name}' ({os.path.basename(pck_path)})")

    for folder in [RAW_DIR, SHEETS_DIR]:
        if os.path.exists(folder):
            shutil.rmtree(folder)

    # Папку проекта Godot НЕ удаляем целиком: редактор часто держит её открытой
    # (на Windows это даёт PermissionError), да и кэш .godot пересоздавать незачем.
    # Все генерируемые файлы ниже просто перезаписываются.
    for sub in ["sprites", "objects", "levels", "scripts", "audio", "dialogue"]:
        sub_dir = os.path.join(GODOT_DIR, sub)
        os.makedirs(sub_dir, exist_ok=True)
        for stale in glob.glob(os.path.join(sub_dir, "*")):
            if os.path.isfile(stale):
                try:
                    os.remove(stale)
                except OSError:
                    pass

    print("1/5 Распаковка .pck и склейка спрайт-шитов...")
    sheets_cnt = unpack_pck_and_build_sheets(pck_path)

    print("2/5 Синтез 8-битного звука (.sng -> .wav) и сбор диалогов...")
    audio_files = export_audio()
    sprite_info = export_sprites()
    popups = collect_popups()

    print("3/5 Сборка объектов, коллизий и HUD...")
    created_objs, hud_widget_objs = build_objects(sprite_info, audio_files)

    print("4/5 Генерация уровней и подмешивание общего GUI...")
    first_lvl, level_flow = build_levels(created_objs, hud_widget_objs, audio_files)

    print("5/5 Генерация GDScript-шаблонов и project.godot...")
    write_gamestate(popups, level_flow)
    write_player_script()
    write_entity_scripts()
    write_ui_script()
    write_dialogues(popups)

    # Пользовательские правки поверх сгенерированных файлов.
    # Положи, например, подправленную сцену в workspace/overrides/objects/Obj_....tscn —
    # она переживёт любой перезапуск конвертера.
    applied = []
    for sub in ["objects", "scripts", "levels", "sprites", "audio", "dialogue"]:
        src_dir = os.path.join(OVERRIDES_DIR, sub)
        if not os.path.isdir(src_dir):
            continue
        dst_dir = os.path.join(GODOT_DIR, sub)
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(os.listdir(src_dir)):
            src = os.path.join(src_dir, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dst_dir, name))
                applied.append(f"{sub}/{name}")
    if applied:
        print(f"Применено пользовательских оверрайдов: {len(applied)} ({', '.join(applied[:3])}{'...' if len(applied) > 3 else ''})")

    dm_dir = os.path.join(GODOT_DIR, "addons", "dialogue_manager")
    dm_script = next(
        (n for n in os.listdir(dm_dir) if n.lower() == "dialogue_manager.gd"),
        None,
    ) if os.path.isdir(dm_dir) else None
    dm_autoload = f'DialogueManager="*res://addons/dialogue_manager/{dm_script}"\n' if dm_script else ""
    dm_plugin = ""
    if os.path.exists(os.path.join(dm_dir, "plugin.cfg")):
        dm_plugin = '[editor_plugins]\nenabled=PackedStringArray("res://addons/dialogue_manager/plugin.cfg")\n'

    with open(os.path.join(GODOT_DIR, "project.godot"), "w", encoding="utf-8") as f:
        f.write(
            f'config_version=5\n[application]\nconfig/name="{game_name}"\n'
            f'run/main_scene="{first_lvl}"\nconfig/features=PackedStringArray("4.7")\n'
            f'[autoload]\nGameState="*res://scripts/GameState.gd"\n'
            f'{dm_autoload}'
            f'{dm_plugin}'
            f'[display]\n'
            f'window/size/viewport_width=480\nwindow/size/viewport_height=320\n'
            f'window/stretch/mode="viewport"\nwindow/stretch/aspect="expand"\n'
            f'[rendering]\ntextures/canvas_textures/default_texture_filter=0\n'
        )
    print(f"\nУспех! Спрайт-шитов: {sheets_cnt} | Объектов: {len(created_objs)} | Уровней: {len(level_flow['order'])}")

if __name__ == "__main__":
    main()
