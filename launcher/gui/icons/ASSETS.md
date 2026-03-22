# WOPC Design Asset Library

Pre-converted PNGs from game source textures for use in the Python launcher GUI.
Source: `vendor/faf-ui/textures/ui/` (DDS originals).

## Map Markers (for canvas preview)

| File | Size | Source | Usage |
|------|------|--------|-------|
| `marker_mass.png` | 32×32 | `icons_strategic/structure_mass.dds` | Mass deposit markers on map preview |
| `marker_hydro.png` | 32×32 | `icons_strategic/structure_energy.dds` | Hydrocarbon markers on map preview |
| `marker_commander.png` | 32×32 | `icons_strategic/commander_generic.dds` | Spawn/army position markers on map preview |

## Faction Icons

| File | Size | Source | Usage |
|------|------|--------|-------|
| `faction_aeon.png` | 64×64 | `faction_icon-lg/aeon_med.png` | Faction selector, player slots |
| `faction_cybran.png` | 64×64 | `faction_icon-lg/cybran_med.png` | Faction selector, player slots |
| `faction_uef.png` | 64×64 | `faction_icon-lg/uef_med.png` | Faction selector, player slots |
| `faction_seraphim.png` | 64×64 | `faction_icon-lg/seraphim_med.png` | Faction selector, player slots |
| `faction_random.png` | 18×18 | `faction_icon-sm/random_ico.dds` | Random faction option |

## Source Asset Index

Full inventory of available textures for future use.

### Strategic Icons (`vendor/faf-ui/textures/ui/icons_strategic/`)
80 icons, all 32×32 RGBA DDS. Categories:
- **Resources**: `structure_mass`, `structure_massfab`, `structure_massstorage`, `structure_energy`, `structure_energystorage`
- **Commander**: `commander_generic`
- **Factories**: `factory_{air,land,naval,generic}`, `factory_{air,land,naval,generic}hq`
- **Structures**: `structure_{antiair,antimissile,antinavy,artillery,counterintel,directfire,engineer,generic,generichq,intel,shield,transport,wall}`
- **Land units**: `land_{antiair,antishield,artillery,bomb,counterintel,directfire,engineer,generic,intel,missile,shield}`, `bot_*`
- **Air units**: `bomber_*`, `fighter_*`, `gunship_*`
- **Naval**: `ship_*`, `sub_*`
- **Other**: `experimental_generic`, numbered files `1`, `2`, `3`

### State-Variant Icons (`vendor/faf-ui/textures/ui/common/game/strategicicons/`)
1300 files. Each icon has 4 states: `_rest`, `_over`, `_selected`, `_selectedover`.
Named: `icon_{category}{tier}_{type}_{state}.dds`
Tiers: 1, 2, 3 (or no tier = generic).

### In-Game Splat Markers (`vendor/faf-ui/env/Common/splats/`)
- `mass_marker.dds` — 256×256, in-game mass deposit ring texture
- `hydrocarbon_marker.dds` — 256×256, in-game hydro plant ring texture

### Faction Icons (`vendor/faf-ui/textures/ui/common/faction_icon-lg/`)
Pre-existing PNGs (no conversion needed):
- `{faction}_med.png` — 64×64, medium faction emblem (aeon, cybran, uef, seraphim)
- `{faction}_mini.png` — 64×64, mini faction emblem
- `{faction}_thick.png` — 64×64, thick-bordered emblem

### Faction Icons Small (`vendor/faf-ui/textures/ui/common/faction_icon-sm/`)
- `{faction}_ico.dds` — 18×18, tiny faction icon (aeon, cybran, uef, seraphim, random)

### Faction Backgrounds (`vendor/faf-ui/textures/ui/common/BACKGROUND/faction/`)
- `faction-background-paint_{faction}_bmp.dds` — large faction-themed backgrounds

### Lobby Chrome / 9-Slice Frame (`vendor/faf-ui/textures/ui/UEF/scx_menu/lan-game-lobby/`)
UEF metallic SupCom frame borders (9-slice pattern):
- `frame/topLeft.dds` (80×80), `frame/top.dds` (60×80, tileable)
- `frame/topRight.dds`, `frame/left.dds`, `frame/right.dds`
- `frame/bottomLeft.dds`, `frame/bottom.dds`, `frame/bottomRight.dds`
- `dialog/background/` — same structure for dialog panels
- `lobby.dds` — 1024×768 full lobby background
- `wide.dds` — widescreen variant

Other factions (AEON, CYBRAN, SERAPHIM) have their own `scx_menu/` with similar structures.

### Health/Shield Bars (`vendor/faf-ui/textures/ui/common/game/avatar/`)
- `health-bar-{green,red,yellow}.dds`, `shield-bar-blue.dds`

## Converting New Assets

Use PIL to convert DDS → PNG:
```python
from PIL import Image
Image.open("source.dds").save("target.png")
```

Or run the conversion script:
```bash
.venv/Scripts/python.exe _convert_icons.py
```
