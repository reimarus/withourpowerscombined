# WOPC - With Our Powers Combined

**Standalone Supreme Commander: Forged Alliance with engine patches, extended content, and a modern launcher**

WOPC is a self-contained distribution of Supreme Commander: Forged Alliance. It combines community-developed engine patches (collision fixes, memory improvements, Lua API extensions) with curated gameplay content (hundreds of additional units, maps, and AI improvements) into a single launcher that handles everything automatically.

---

## Download & Play

### What you need

1. **Supreme Commander: Forged Alliance** on Steam (must be installed)
2. **Windows 10/11**

That's it — no Python or other tools needed.

### First-time setup

1. **Download** `WOPC-Launcher.exe` from the [latest release](https://github.com/reimarus/withourpowerscombined/releases/latest)
2. **Run it** — Windows may show a SmartScreen warning; click "More info" → "Run anyway"
3. **Click Install** — the launcher downloads all game content (~500 MB) automatically. This takes a few minutes the first time.
4. **Click Play** to launch a solo game, or switch to **Multiplayer** to host/join LAN games

### Staying up to date

The launcher handles everything automatically. It checks for updates on startup and will update itself and game content when new versions are available — no need to visit GitHub again.

### Playing multiplayer

1. Make sure all players have the **same version** (everyone clicks Install if prompted)
2. One player clicks **Multiplayer → Create Game** (they become the host)
3. Other players on the same LAN click **Multiplayer** and the game appears automatically in the browser
4. Not on the same LAN? Expand **Direct Connect** and enter the host's IP address
5. Once everyone is in the lobby, the host clicks **Launch Game**

---

## Developer Setup

If you want to contribute or build from source:

### Requirements

- Python 3.10+
- Supreme Commander: Forged Alliance on Steam

### Building the launcher

```
git clone https://github.com/reimarus/withourpowerscombined.git
cd withourpowerscombined
pip install -r requirements.txt
python build_exe.py            # Produces dist\WOPC-Launcher.exe
```

Or run directly without building:
```
python -m launcher.gui
```

### CLI tools

```
cd launcher
python wopc.py status     # Detect game installation, print paths
python wopc.py setup      # Create C:\ProgramData\WOPC\, copy game files
python wopc.py launch     # Start the game
```

## How It Works

WOPC creates an isolated game directory at `C:\ProgramData\WOPC\` containing:
- A copy of the game executable and engine DLLs (from your Steam installation)
- Gameplay content (downloaded from GitHub Releases)
- A custom init file (`init_wopc.lua`) that loads content in the correct order
- A WOPC overlay layer for our own patches
- Content pack mods (BlackOps, TotalMayhem, etc.)

**Your Steam SCFA installation is never modified.**

## Project Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Project foundation, binary patches integration |
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
    SupremeCommander.exe                (copied from Steam)
    init_wopc.lua                       (custom init file)
    CommonDataPath.lua                  (VFS helper functions)
    MohoEngine.dll + other DLLs        (copied from Steam)
  gamedata\
    wopc_core.scd                      (downloaded from GitHub or built locally)
    blackops.scd, TotalMayhem.scd      (downloaded from GitHub)
    content_icons.scd                  (unit icons for content packs)
  maps\                                (downloaded from GitHub)
  sounds\                              (downloaded from GitHub)
  usermods\                            (extracted from content pack SCDs)
```

## Content Mount Order

The init file loads content in this order (later entries shadow earlier ones):

1. Bundled strategic icons
2. Content pack gamedata SCDs (lua.scd, units.scd, brewlan.scd, etc.)
3. Bundled maps and sounds
4. Vanilla SCFA content (fonts, textures, effects, meshes, movies)
5. **WOPC core** (game logic, patches, and enhancements)
6. User maps
7. User mods (BetterPathing, etc.)

## Contributing

See [docs/architecture.md](docs/architecture.md) for the technical plan and [docs/backlog.md](docs/backlog.md) for what's next.

## License

MIT License - see [LICENSE](LICENSE).

## Credits

- **SupCom modding community** — the foundation this project builds on
- **Gas Powered Games** — original Supreme Commander: Forged Alliance
