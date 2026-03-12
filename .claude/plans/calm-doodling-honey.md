# Feature: Persistent minimap visibility toggle in launcher

## Context

The user wants a **persistent player setting** in the WOPC launcher to control
whether the minimap is visible when the game starts. Currently the only way to
toggle the minimap is with the in-game hotkey after the match has loaded. This
setting should be saved across sessions so the player doesn't have to toggle it
every game.

**How the minimap works today:** FAF's `minimap.lua` (line 20) reads
`Prefs.GetFromCurrentProfile('stratview')` at module load time. If `false`
(default), `CreateMinimap()` hides the minimap panel. The in-game toggle saves
back to profile prefs. We need to set this profile pref **before** the game UI
is created.

## Changes

### 1. Add `minimap_enabled` to prefs (`launcher/prefs.py`)

Add to `DEFAULT_PREFS["Game"]`:

```python
"Game": {
    "active_map": "",
    "player_name": "Player",
    "minimap_enabled": "True",   # <-- ADD (default: show minimap)
},
```

Add a getter helper:

```python
def get_minimap_enabled() -> bool:
    parser = load_prefs()
    return parser.getboolean("Game", "minimap_enabled", fallback=True)
```

### 2. Add minimap checkbox to launcher GUI (`launcher/gui/app.py`)

Add a "PLAYER SETTINGS" section in the right pane (`_build_mod_pane`), below
the user mods section. Use a `CTkCheckBox` bound to the pref:

```python
# --- Player Settings Section ---
self.settings_header = ctk.CTkLabel(
    self.mod_pane, text="PLAYER SETTINGS",
    text_color=COLOR_TEXT_MUTED,
    font=ctk.CTkFont(size=12, weight="bold"),
)

self.minimap_var = ctk.BooleanVar(value=prefs.get_minimap_enabled())
self.minimap_cb = ctk.CTkCheckBox(
    self.mod_pane, text="Show minimap on launch",
    variable=self.minimap_var,
    command=self._on_minimap_toggle,
)
```

Add handler:

```python
def _on_minimap_toggle(self) -> None:
    parser = prefs.load_prefs()
    parser.set("Game", "minimap_enabled", str(self.minimap_var.get()))
    prefs.save_prefs(parser)
```

### 3. Pass setting through game config (`launcher/wopc.py`)

In `cmd_launch()`, read the pref and pass it as a game option:

```python
minimap_enabled = prefs.get_minimap_enabled()
config_path = write_game_config(
    scenario_file=vfs_path,
    player_name=player_name,
    game_options={"minimap_enabled": str(minimap_enabled)},
)
```

This writes `minimap_enabled = 'True'` (or `'False'`) into `wopc_game_config.lua`.

### 4. Set profile pref in quickstart (`gamedata/wopc_patches/lua/wopc/quickstart.lua`)

In the `Launch()` function, after loading config but **before** calling
`comm:LaunchGame()`, read the game option and set the engine profile pref:

```lua
-- Apply WOPC player settings to engine profile prefs
if cfg.GameOptions then
    local Prefs = import('/lua/user/prefs.lua')
    if cfg.GameOptions.minimap_enabled then
        local enabled = (cfg.GameOptions.minimap_enabled == 'True')
        Prefs.SetToCurrentProfile('stratview', enabled)
        LOG('WOPC: Set minimap visibility to ' .. tostring(enabled))
    end
end
```

This runs in the lobby UI state, before `LaunchGame()` transitions to game
state. When `minimap.lua` is later imported in game state, it reads the
updated `stratview` pref and shows/hides the minimap accordingly.

## Files to modify

| File | Change |
|------|--------|
| `launcher/prefs.py` | Add `minimap_enabled` default + `get_minimap_enabled()` helper |
| `launcher/gui/app.py` | Add "PLAYER SETTINGS" section with minimap checkbox |
| `launcher/wopc.py` | Pass `minimap_enabled` in `game_options` dict |
| `gamedata/wopc_patches/lua/wopc/quickstart.lua` | Set `stratview` profile pref from game option |

## Not in scope

- Other player settings (these can be added to the same section later)
- In-game toggle hotkey (already works via FAF's minimap.lua)

## Verification

1. `pytest tests/ -x -q` — all pass
2. `ruff check launcher/ tests/` — clean
3. Rebuild exe: `python build_exe.py`
4. Launch GUI — verify "PLAYER SETTINGS" section with minimap checkbox appears
5. Uncheck minimap, launch match — minimap should be hidden
6. Check minimap, launch match — minimap should be visible
7. Restart launcher — checkbox should remember the last setting
