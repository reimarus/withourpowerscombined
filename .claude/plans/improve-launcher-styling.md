# Plan: WOPC Launcher — FAF/SupCom Visual Redesign

## Context
The WOPC launcher GUI (`launcher/gui/app.py`) currently uses a generic Discord color scheme
(purple blurple, Discord green, grey panels) that has no thematic connection to Supreme Commander:
Forged Alliance. The user wants a full visual redesign taking cues from the FAF client aesthetic:
deep space navy backgrounds, gold/amber accents (FAF's signature), electric cyan secondary
accents, angular military styling, and improved visual hierarchy throughout.

## Target Palette (FAF/SupCom Aesthetic)

Replace all 8 color constants at lines 35–43 with:

```python
COLOR_BG       = "#080C14"   # Deep space black-navy (sidebar)
COLOR_PANEL    = "#0D1220"   # Dark navy main background
COLOR_MOD_PANEL= "#111827"   # Secondary panel (mod pane, cards)
COLOR_SURFACE  = "#162030"   # Card/elevated surface
COLOR_BORDER   = "#1E2D42"   # Subtle panel border
COLOR_ACCENT   = "#C8A84B"   # FAF Gold — primary interactive
COLOR_ACCENT_HOVER = "#E8C870"  # Gold hover state
COLOR_ACCENT_DIM   = "#6B5A28"  # Dimmed gold for decorative lines
COLOR_READY    = "#C8A84B"   # Gold — PLAY MATCH (same as accent)
COLOR_LAUNCH   = "#4DC3F5"   # Electric cyan — LAUNCH GAME in lobby
COLOR_WARN     = "#FF8C42"   # Orange — warning state
COLOR_DANGER   = "#E84855"   # Red — LEAVE / destructive actions
COLOR_TEXT_PRIMARY = "#E8E4D4"  # Warm cream (not cold white)
COLOR_TEXT_MUTED   = "#4A5A70"  # Muted navy-grey
COLOR_TEXT_GOLD    = "#C8A84B"  # Gold text (headers, section labels)
```

## Critical File
**`/home/user/withourpowerscombined/launcher/gui/app.py`** — all changes in this single file.

## Changes by Section

### 1. Color Constants (lines 35–43)
- Replace the 8 existing constants with the 15 new ones above
- Add `COLOR_SURFACE`, `COLOR_BORDER`, `COLOR_ACCENT_HOVER`, `COLOR_ACCENT_DIM`,
  `COLOR_LAUNCH`, `COLOR_DANGER`, `COLOR_TEXT_GOLD` as new constants
- Remove old hover hardcodes like `"#4752C4"`, `"#1F8B4C"`, `"#C53030"` — use new constants

### 2. New Helper: `_make_divider(parent)` method
Add a small helper method to the class that returns a thin accent separator frame:
```python
def _make_divider(self, parent: Any, color: str = COLOR_ACCENT_DIM) -> Any:
    return ctk.CTkFrame(parent, fg_color=color, height=1, corner_radius=0)
```
Used to draw gold horizontal rules between sidebar sections and panel headers.

### 3. `_build_sidebar()` Redesign (lines 155–276)

**Logo treatment:**
- Change `logo_label` text color from `COLOR_TEXT_PRIMARY` (white) → `COLOR_TEXT_GOLD` (gold)
- Increase logo font to size=32 for more presence
- Add a gold divider (`_make_divider`) below the subtitle row (new row 2)
- Change subtitle text from `"LOBBY TERMINAL"` → `"WITH OUR POWERS COMBINED"` (or keep, but style in dim gold)
- Subtitle text color: `COLOR_ACCENT_DIM`

**Sidebar frame:**
- Add `border_width=0` (keep) but use `fg_color=COLOR_BG` (deepen from `#1E1F22` to `#080C14`)

**Status indicators (rows 2–4):**
- Prefix each status label with a Unicode dot: `"● SCFA: Checking..."` in muted color
- When status updates, use `"✓ SCFA: Ready"` (green text), `"✗ SCFA: Missing"` (danger red)
- Change status text color from constant `COLOR_TEXT_MUTED` to dynamic color per state

**Section label "LAUNCH MODE" (row 5):**
- Change `text_color` from `COLOR_TEXT_MUTED` → `COLOR_TEXT_GOLD`
- Add a divider above it (new row before the label)

**Mode selector segmented button:**
- Add `selected_color=COLOR_ACCENT`, `selected_hover_color=COLOR_ACCENT_HOVER`
- Add `unselected_color=COLOR_SURFACE`, `fg_color=COLOR_BORDER`

**Play button (row 8):**
- Change `fg_color=COLOR_READY` (now gold `#C8A84B`), `hover_color=COLOR_ACCENT_HOVER`
- Change font to size=16 (was 18; more refined)
- Height stays 50

**Version label:**
- Change `text_color` → `COLOR_ACCENT_DIM`

### 4. `_build_main_lobby()` — Solo Screen

**Header "Game Configuration":**
- Change `text_color` → `COLOR_TEXT_GOLD`
- Font size 20 (unchanged)
- Add a gold divider below header (new row)

**Config panel (map selector):**
- Change `fg_color=COLOR_MOD_PANEL` → `COLOR_SURFACE`
- Change `corner_radius=8` → `4` (more angular)

**Selected map label:**
- `text_color=COLOR_ACCENT` → stays gold (already correct conceptually, but ensure it uses new `COLOR_ACCENT`)

**Lower panel (player slots + game options):**
- `fg_color=COLOR_MOD_PANEL` → `COLOR_SURFACE`
- `corner_radius=8` → `4`

**Log textbox:**
- `fg_color=COLOR_MOD_PANEL` → `COLOR_PANEL` (deeper background for log area)
- `text_color=COLOR_TEXT_MUTED` → keep (muted is fine for log output)

**"PLAYERS" section label** (in `_build_player_slots()`):
- `text_color=COLOR_TEXT_MUTED` → `COLOR_TEXT_GOLD`

**"+ Add AI" button:**
- `fg_color=COLOR_ACCENT` → keep (gold is correct)

### 5. `_build_browser_screen()`

**"Find a Game" header:**
- `text_color=COLOR_TEXT_PRIMARY` → `COLOR_TEXT_GOLD`
- Font size 24 → 22 (tighter)

**Game list frame:**
- `fg_color=COLOR_MOD_PANEL` → `COLOR_SURFACE`, `corner_radius=8` → `4`

**"CREATE GAME" button:**
- `fg_color=COLOR_READY` (now gold), `hover_color=COLOR_ACCENT_HOVER`

**"Connect" button in direct connect:**
- `fg_color=COLOR_ACCENT` → stays (gold)

### 6. `_build_lobby_screen()`

All 4 sub-frames (map, players, opts, chat):
- `fg_color=COLOR_MOD_PANEL` → `COLOR_SURFACE`
- `corner_radius=8` → `4`

**Section header labels** (MAP, PLAYERS, GAME OPTIONS, CHAT):
- `text_color=COLOR_TEXT_MUTED` → `COLOR_TEXT_GOLD`

**"Change Map" button:**
- `fg_color=COLOR_ACCENT` → stays gold

**"+ Add AI" button in lobby:**
- `fg_color=COLOR_ACCENT` → stays gold

**"LEAVE" button:**
- `fg_color="#ED4245"` → `COLOR_DANGER` (use constant)
- `hover_color="#C53030"` → `"#BF3040"` or `COLOR_DANGER` hover

**"LAUNCH GAME" button:**
- `fg_color=COLOR_READY` → `COLOR_LAUNCH` (cyan `#4DC3F5`) — differentiate from the gold PLAY button
- `hover_color="#1F8B4C"` → `"#35A8D8"`

### 7. `_build_mod_pane()`

**Section headers (CONTENT PACKS, USER MODS, PLAYER SETTINGS):**
- `text_color=COLOR_TEXT_MUTED` → `COLOR_TEXT_GOLD`
- Add `_make_divider` above each section header

**Mod pane background:**
- `fg_color=COLOR_MOD_PANEL` → `COLOR_BG` (match sidebar = deepest level)

### 8. `_check_installation_status()` and `_update_status_label()`
The existing `_check_installation_status` method updates `status_scfa`, `status_bundled`,
`status_wopc` labels. Update the display format:
- Ready state: `"✓ SCFA: Ready"` with `text_color="#4DC3F5"` (cyan)
- Missing state: `"✗ SCFA: Missing"` with `text_color=COLOR_DANGER`
- Checking state: `"◌ SCFA: Checking..."` with `text_color=COLOR_TEXT_MUTED`

### 9. `configure(fg_color=...)` on main window
- Line 101: `self.configure(fg_color=COLOR_PANEL)` → `fg_color=COLOR_BG` (deepen root window)

## Hover Colors to Inline-Replace
These hardcoded hover colors must change:
| Old | New |
|-----|-----|
| `"#4752C4"` (Discord blurple hover) | `COLOR_ACCENT_HOVER` |
| `"#1F8B4C"` (Discord green hover) | `COLOR_ACCENT_HOVER` |
| `"#C53030"` (red hover) | `"#BF3040"` |

## Map Button Styling (`_refresh_map_list`)
When map buttons are created (dynamically), update:
- Selected map button: `fg_color=COLOR_ACCENT`, `hover_color=COLOR_ACCENT_HOVER`
- Unselected map button: `fg_color=COLOR_SURFACE`, `hover_color=COLOR_BORDER`

## Verification / Testing
1. Run from dev mode: `.venv/Scripts/python.exe -c "from launcher.gui.app import launch_gui; launch_gui()"`
2. Check all 3 screens (Solo / Browser / Lobby) render with new color scheme
3. Check status indicators update from "Checking" → Ready/Missing with correct colors
4. Verify play button is gold, launch button is cyan, leave button is red
5. Run `pytest` — no functional tests should break (pure visual change)
6. Run `ruff check launcher/` — no lint errors
7. Run `mypy launcher/` — no type errors
8. Rebuild exe: `python build_exe.py`

## Out of Scope
- No layout structure changes (grid stays 3-column)
- No new dependencies (no PIL/Pillow, no tkinter Canvas drawings)
- No widget type changes
- No functional/networking changes

## Git
- Branch: `claude/improve-launcher-styling-WdUEC`
- Commit plan first, then implement
- Push to `claude/improve-launcher-styling-WdUEC`
