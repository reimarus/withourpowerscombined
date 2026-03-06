# WOPC - With Our Powers Combined

**LOUD gameplay + FAF engine patches for Supreme Commander: Forged Alliance**

WOPC merges two community projects that independently improved Supreme Commander: Forged Alliance:

- **[LOUD](https://github.com/LOUD-Project/Git-LOUD)** - A complete gameplay overhaul: 545 rewritten Lua files, AI from scratch, 17 content packs adding hundreds of units, and aggressive performance optimization.
- **[FAF (Forged Alliance Forever)](https://github.com/FAForever)** - Binary patches to the compiled C++ engine: collision fixes, Lua API extensions, and 10-15% performance improvement at the engine level.

Neither project benefits from the other today. WOPC combines them into a single self-contained distribution and provides a foundation for **replacing the game's compiled C++ subsystems** (pathfinding, steering, collision) one at a time.

## Quick Start

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
| 0 | Complete | Project foundation - launcher, init file, repo structure |
| 1 | Complete | Validate LOUD gameplay works from WOPC directory |
| 2 | Complete | Integrate FAF binary patches - patched exe with engine improvements |
| 3 | Complete | WOPC Lua overlay - compatibility patches, new features |
| 4 | Complete | Multiplayer support - content manifests, version checking |
| 5 | Planned | First C++ engine patch - pathfinding improvement |
| 6 | Complete | WOPC Advanced Launcher - GUI, discrete mod selection |
| 7 | Complete | Match Lobby - Discord UI, standalone direct launch |
| 8 | Planned | Deep C++ Refactoring - rendering optimizations, simulation speed |

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

This project is in early development. See [docs/architecture.md](docs/architecture.md) for the technical plan and [docs/setup-guide.md](docs/setup-guide.md) for development setup.

## License

MIT License - see [LICENSE](LICENSE).

## Credits

- **LOUD Project** - Gameplay content, AI, and performance optimization
- **Forged Alliance Forever** - Binary patching infrastructure and engine improvements
- **Gas Powered Games** - Original Supreme Commander: Forged Alliance
