# GameCreator (Android) to Godot 4 Converter

Automated reverse-engineering and porting tool that converts projects created in the mobile engine **Game Creator (SilentWorks)** directly into a playable **Godot 4.7+** project.

## Features
* **Binary `.pck` Unpacker:** Extracts sprites (`.frm`), sprite configs (`.spr`), objects (`.obj`), levels (`.led`/`.lei`), and raw PCM audio (`.sng`).
* **Palette Restoration & Sprite Sheets:** Decodes 8-bit indexed pixel arrays using Game Creator's 256-color palette (with transparency) and stitches animation frames into horizontal sprite sheets.
* **Multi-Genre Support:** Automatically generates GDScript controllers for **Platformer** (melee & ranged combat), **RPG / Top-View**, and **Scroller Shooter** modes.
* **Level & Logic Reconstruction:** Preserves gradients, fixed parallax backgrounds, invisible walls, switches (`listener` -> `number` events), doors, teleports, pop-up dialogues, timers, and HUD widgets (Health, Score).
* **Audio Conversion:** Converts raw 8-bit `.sng` sound effects and music tracks into standard `.wav` files.

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Place your Game Creator files (`.pck`, `.gcg`, `.gci`, `.gcl`, `.gcv`) into `workspace/input_game/`.
3. Run the converter:
   ```bash
   python main.py
   ```
4. Open **Godot 4.7+** and import `workspace/GodotProject/project.godot`.
