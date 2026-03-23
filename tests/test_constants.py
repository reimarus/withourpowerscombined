"""Tests for launcher.gui.constants — color conversions and option mappings."""

from __future__ import annotations

from launcher.gui.constants import (
    AI_DISPLAY_NAMES,
    FACTION_NAMES,
    FOG_MAP,
    GAME_OPTION_DEFS,
    PLAYER_COLORS,
    SPEED_MAP,
    VICTORY_DESCRIPTIONS,
    VICTORY_MAP,
    color_hex_to_index,
    color_index_to_hex,
    color_name_to_hex,
    game_options_to_engine,
)


class TestPlayerColors:
    """Verify palette structure and constraints."""

    def test_eight_colors(self) -> None:
        assert len(PLAYER_COLORS) == 8

    def test_unique_hex_values(self) -> None:
        hexes = [h for h, _ in PLAYER_COLORS]
        assert len(set(hexes)) == 8

    def test_unique_names(self) -> None:
        names = [n for _, n in PLAYER_COLORS]
        assert len(set(names)) == 8

    def test_hex_format(self) -> None:
        for hex_val, _ in PLAYER_COLORS:
            assert hex_val.startswith("#")
            assert len(hex_val) == 7


class TestColorNameToHex:
    """Tests for color_name_to_hex()."""

    def test_known_name(self) -> None:
        assert color_name_to_hex("Red") == "#FF0000"
        assert color_name_to_hex("Blue") == "#0000FF"

    def test_passthrough_hex(self) -> None:
        assert color_name_to_hex("#ABCDEF") == "#ABCDEF"

    def test_unknown_name_returns_first(self) -> None:
        assert color_name_to_hex("Magenta") == PLAYER_COLORS[0][0]


class TestColorHexToIndex:
    """Tests for color_hex_to_index()."""

    def test_exact_hex_match(self) -> None:
        for i, (hex_val, _) in enumerate(PLAYER_COLORS):
            assert color_hex_to_index(hex_val) == i + 1

    def test_exact_name_match(self) -> None:
        for i, (_, name) in enumerate(PLAYER_COLORS):
            assert color_hex_to_index(name) == i + 1

    def test_nearest_rgb_distance(self) -> None:
        # Very close to Red (#FF0000)
        assert color_hex_to_index("#FE0101") == 1

    def test_nearest_to_green(self) -> None:
        # Close to Green (#00FF00)
        assert color_hex_to_index("#00FE00") == 8  # Green is index 8

    def test_unknown_string_returns_1(self) -> None:
        assert color_hex_to_index("garbage") == 1

    def test_short_hex_returns_1(self) -> None:
        assert color_hex_to_index("#FFF") == 1


class TestColorIndexToHex:
    """Tests for color_index_to_hex()."""

    def test_valid_indices(self) -> None:
        for i in range(1, 9):
            assert color_index_to_hex(i) == PLAYER_COLORS[i - 1][0]

    def test_clamp_low(self) -> None:
        assert color_index_to_hex(0) == PLAYER_COLORS[0][0]
        assert color_index_to_hex(-5) == PLAYER_COLORS[0][0]

    def test_clamp_high(self) -> None:
        assert color_index_to_hex(99) == PLAYER_COLORS[-1][0]


class TestGameOptionsToEngine:
    """Tests for game_options_to_engine()."""

    def test_victory_mapping(self) -> None:
        result = game_options_to_engine({"Victory": "Supremacy"})
        assert result["Victory"] == "domination"

    def test_fog_mapping(self) -> None:
        result = game_options_to_engine({"FogOfWar": "Explored"})
        assert result["FogOfWar"] == "explored"

    def test_speed_mapping(self) -> None:
        result = game_options_to_engine({"GameSpeed": "Fast"})
        assert result["GameSpeed"] == "fast"

    def test_passthrough_keys(self) -> None:
        result = game_options_to_engine({"UnitCap": "1500", "Share": "FullShare"})
        assert result["UnitCap"] == "1500"
        assert result["Share"] == "FullShare"

    def test_unknown_victory_lowercased(self) -> None:
        result = game_options_to_engine({"Victory": "CustomMode"})
        assert result["Victory"] == "custommode"

    def test_all_victory_types_have_descriptions(self) -> None:
        victory_opt = next(d for d in GAME_OPTION_DEFS if d[0] == "Victory")
        for val in victory_opt[2]:
            assert val in VICTORY_DESCRIPTIONS
            assert val in VICTORY_MAP


class TestListConstants:
    """Verify list constants have expected entries."""

    def test_faction_names(self) -> None:
        assert "Random" in FACTION_NAMES
        assert "UEF" in FACTION_NAMES
        assert len(FACTION_NAMES) == 5

    def test_ai_display_names(self) -> None:
        assert "Easy" in AI_DISPLAY_NAMES
        assert "Random" in AI_DISPLAY_NAMES
        assert len(AI_DISPLAY_NAMES) >= 5

    def test_game_option_defs_structure(self) -> None:
        for key, label, values, default in GAME_OPTION_DEFS:
            assert isinstance(key, str)
            assert isinstance(label, str)
            assert isinstance(values, list)
            assert default in values

    def test_all_fog_values_mapped(self) -> None:
        fog_opt = next(d for d in GAME_OPTION_DEFS if d[0] == "FogOfWar")
        for val in fog_opt[2]:
            assert val in FOG_MAP

    def test_all_speed_values_mapped(self) -> None:
        speed_opt = next(d for d in GAME_OPTION_DEFS if d[0] == "GameSpeed")
        for val in speed_opt[2]:
            assert val in SPEED_MAP
