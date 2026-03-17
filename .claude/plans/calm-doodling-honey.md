# Feature: Faction selector in launcher

## Context

The user needs to choose a faction (UEF, Aeon, Cybran, Seraphim, Random) from
the launcher to test faction-specific bugs (e.g. Aeon freeze). Currently
`write_game_config()` already supports a `player_faction` parameter but it's
never passed — defaulting to "random".

## Changes

### 1. Add `player_faction` to prefs (`launcher/prefs.py`)

Add to `DEFAULT_PREFS["Game"]` (after `minimap_enabled`):
```python
"player_faction": "random",
```

Add getter:
```python
def get_player_faction() -> str:
    parser = load_prefs()
    return parser.get("Game", "player_faction", fallback="random")
```

### 2. Add faction dropdown to GUI (`launcher/gui/app.py`)

In `_build_mod_pane()`, add a `CTkOptionMenu` in the PLAYER SETTINGS section
(insert at row 5, shift minimap to row 6, summary to row 7):

```python
self.faction_var = ctk.StringVar(value=prefs.get_player_faction().capitalize())
self.faction_menu = ctk.CTkOptionMenu(
    self.mod_pane,
    values=["Random", "UEF", "Aeon", "Cybran", "Seraphim"],
    variable=self.faction_var,
    command=self._on_faction_change,
    width=160,
)
```

Add handler (same pattern as `_on_minimap_toggle`):
```python
def _on_faction_change(self, choice: str) -> None:
    parser = prefs.load_prefs()
    parser.set("Game", "player_faction", choice.lower())
    prefs.save_prefs(parser)
```

### 3. Pass faction to game config (`launcher/wopc.py`)

In `cmd_launch()` (after `minimap_enabled`):
```python
player_faction = prefs.get_player_faction()
```
Add to `write_game_config()` call:
```python
player_faction=player_faction,
```

**No changes needed** to `game_config.py` — already supports `player_faction`.

## Files to modify

| File | Change |
|------|--------|
| `launcher/prefs.py` | Add `player_faction` default + getter |
| `launcher/gui/app.py` | Add faction dropdown in PLAYER SETTINGS |
| `launcher/wopc.py` | Pass `player_faction` to `write_game_config()` |

## Verification

1. `pytest tests/ -x -q` — all pass
2. `ruff check` — clean
3. Launch GUI — faction dropdown appears with Random/UEF/Aeon/Cybran/Seraphim
4. Select Aeon, launch — `wopc_game_config.lua` has `Faction = 2`
5. Restart launcher — dropdown remembers last selection
