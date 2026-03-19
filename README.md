# WOPC - With Our Powers Combined

**LOUD gameplay + FAF engine patches for Supreme Commander: Forged Alliance**

WOPC merges two community projects that independently improved Supreme Commander: Forged Alliance:

- **[LOUD](https://github.com/LOUD-Project/Git-LOUD)** - A complete gameplay overhaul: 545 rewritten Lua files, AI from scratch, 17 content packs adding hundreds of units, and aggressive performance optimization.
- **[FAF (Forged Alliance Forever)](https://github.com/FAForever)** - Binary patches to the compiled C++ engine: collision fixes, Lua API extensions, and 10-15% performance improvement at the engine level.

Neither project benefits from the other today. WOPC combines them into a single self-contained distribution and provides a foundation for **replacing the game's compiled C++ subsystems** (pathfinding, steering, collision) one at a time.

---

## Download & Play

### What you need

1. **Supreme Commander: Forged Alliance** on Steam
2. **LOUD** installed ([LOUD install guide](https://github.com/LOUD-Project/Git-LOUD))
3. **Python 3.10+** ([python.org/downloads](https://www.python.org/downloads/))

### First-time setup

1. **Clone this repo** (or download as ZIP and extract):
   ```
   git clone https://github.com/reimarus/withourpowerscombined.git
   cd withourpowerscombined
   ```

2. **Run the launcher**:
   ```
   python build_exe.py
   dist\WOPC-Launcher.exe
   ```
   Or run directly without building the `.exe`:
   ```
   pip install -r requirements.txt
   python -m launcher.gui
   ```

3. **Click Install** in the launcher. It will detect your Steam and LOUD installations, copy game files to `C:\ProgramData\WOPC\`, and download content packs. This takes a few minutes the first time.

4. **Click Play** to launch a solo game, or switch to **Multiplayer** to host/join LAN games.

### Staying up to date

When we push updates, pull the latest code and rebuild the launcher:

```
cd withourpowerscombined
git pull
python build_exe.py
```

Then open `dist\WOPC-Launcher.exe` and click **Install** again if prompted. The launcher will detect what changed and only update what's needed.

> **Tip:** If you see "UPDATE AVAILABLE" on the Install button, click it before playing to make sure you have the latest patches and content.

### Playing multiplayer

1. Make sure all players are on the **same version** (everyone runs `git pull` + rebuild)
2. One player clicks **Multiplayer → Create Game** (they become the host)
3. Other players on the same LAN click **Multiplayer** and the game appears automatically in the browser
4. Not on the same LAN? Expand **Direct Connect** and enter the host's IP address
5. Once everyone is in the lobby, the host clicks **Launch Game**

---

## Developer Quick Start

```
# Requirements: Python 3.10+, Steam copy of Supreme Commander: Forged Alliance, LOUD installed

cd launcher
python wopc.py status     # Detect game installation, print paths
python wopc.py setup      # Create C:\ProgramData\WOPC\, copy game files
python wopc.py launch     # Start the game with LOUD gameplay
```

## How It Works

WOPC creates an isolated game directory at `C:\ProgramData\WOPC\` containing:
- A copy of the game executable and engine DLLs (from your Steam installation)
- LOUD's gameplay content (symlinked/copied from your LOUD installation)
- A custom init file (`init_wopc.lua`) that loads content in the correct order
- A WOPC overlay layer for our own patches
- Your user mods (like BetterPathing)

**Your Steam SCFA installation and LOUD installation are never modified.**

## Project Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Project foundation, LOUD validation, FAF binary patches |
| 2 | ✅ Complete | WOPC Lua overlay, compatibility patches |
| 3 | ✅ Complete | Multiplayer — content manifests, TCP lobby, file transfer |
| 4 | ✅ Complete | GUI Launcher — install/play, mod selection, map browser |
| 5 | ✅ Complete | Match Lobby — Discord-style UI, standalone direct launch |
| 6 | ✅ Complete | Modern Multiplayer UX — LAN discovery, game browser, lobby room |
| 7 | 🔧 In Progress | Polish — UI styling, player ratings, map library |
| 8 | Planned | C++ Engine Patches — pathfinding, rendering, simulation speed |

See [docs/architecture.md](docs/architecture.md) for the full technical plan.

## Architecture

```
C:\ProgramData\WOPC\                    (isolated game directory)
  bin\
    SupremeCommander.exe                (copied from Steam, later FAF-patched)
    init_wopc.lua                       (custom init file)
    CommonDataPath.lua                  (VFS helper functions)
    MohoEngine.dll + other DLLs        (copied from Steam)
  gamedata\
    lua.scd, units.scd, ...            (symlinked from LOUD)
    wopc_patches.scd                   (WOPC overlay - our enhancements)
  maps\                                (symlinked from LOUD)
  sounds\                              (symlinked from LOUD)
  usermods\                            (copied from LOUD)
```

## Content Mount Order

The init file loads content in this order (later entries shadow earlier ones):

1. BrewLAN strategic icons
2. LOUD gamedata SCDs (lua.scd, units.scd, brewlan.scd, etc.)
3. LOUD maps and sounds
4. Vanilla SCFA content (fonts, textures, effects, meshes, movies)
5. **WOPC patches overlay** (our fixes and enhancements)
6. User mods (BetterPathing, etc.)
7. User maps

## Contributing

See [docs/architecture.md](docs/architecture.md) for the technical plan and [docs/backlog.md](docs/backlog.md) for what's next.

## License

MIT License - see [LICENSE](LICENSE).

## Credits

- **LOUD Project** - Gameplay content, AI, and performance optimization
- **Forged Alliance Forever** - Binary patching infrastructure and engine improvements
- **Gas Powered Games** - Original Supreme Commander: Forged Alliance
