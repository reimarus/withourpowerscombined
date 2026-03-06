"""Tests for launcher.map_scanner."""

from pathlib import Path
from unittest.mock import patch

import pytest

from launcher import map_scanner


@pytest.fixture()
def maps_dir(tmp_path: Path) -> Path:
    """Create a fake maps directory with sample map folders."""
    maps = tmp_path / "maps"
    maps.mkdir()

    # Good map with full metadata
    setons = maps / "Setons Clutch"
    setons.mkdir()
    (setons / "Setons Clutch_scenario.lua").write_text(
        """\
version = 3
ScenarioInfo = {
    name = 'Setons Clutch',
    description = 'A classic naval map.',
    size = {1024, 1024},
    map_version = 1,
    Configurations = {
        ['standard'] = {
            teams = {
                { name = 'FFA',
                  armies = {'ARMY_1','ARMY_2','ARMY_3','ARMY_4',
                             'ARMY_5','ARMY_6','ARMY_7','ARMY_8'} },
            },
        },
    },
}
""",
        encoding="utf-8",
    )

    # Minimal map with no metadata
    minimal = maps / "TestMap"
    minimal.mkdir()
    (minimal / "TestMap_scenario.lua").write_text("ScenarioInfo = {}\n", encoding="utf-8")

    # Directory without scenario file (should be skipped)
    empty = maps / "EmptyFolder"
    empty.mkdir()

    return maps


class TestParseScenario:
    """Tests for parse_scenario()."""

    def test_extracts_full_metadata(self, maps_dir: Path) -> None:
        scenario = maps_dir / "Setons Clutch" / "Setons Clutch_scenario.lua"
        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.display_name == "Setons Clutch"
        assert info.max_players == 8
        assert info.size_label == "40km"
        assert info.description == "A classic naval map."
        assert not info.is_campaign

    def test_handles_missing_metadata(self, maps_dir: Path) -> None:
        scenario = maps_dir / "TestMap" / "TestMap_scenario.lua"
        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.display_name == "TestMap"  # falls back to folder name
        assert info.max_players == 0
        assert info.size_label == "?"
        assert not info.is_campaign

    def test_detects_campaign_prefix(self, tmp_path: Path) -> None:
        scenario_dir = tmp_path / "X1CA_001"
        scenario_dir.mkdir()
        scenario = scenario_dir / "X1CA_001_scenario.lua"
        scenario.write_text("ScenarioInfo = {}", encoding="utf-8")
        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.is_campaign

    def test_returns_none_for_unreadable_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent_scenario.lua"
        info = map_scanner.parse_scenario(missing)
        assert info is None


class TestScanAllMaps:
    """Tests for scan_all_maps()."""

    def test_finds_valid_maps(self, maps_dir: Path) -> None:
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = maps_dir
            results = map_scanner.scan_all_maps()

        # Should find Setons and TestMap but not EmptyFolder
        names = [m.folder_name for m in results]
        assert "Setons Clutch" in names
        assert "TestMap" in names
        assert "EmptyFolder" not in names

    def test_returns_empty_if_no_dir(self, tmp_path: Path) -> None:
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = tmp_path / "nonexistent"
            results = map_scanner.scan_all_maps()
        assert results == []

    def test_results_sorted_by_folder(self, maps_dir: Path) -> None:
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = maps_dir
            results = map_scanner.scan_all_maps()
        folder_names = [m.folder_name for m in results]
        assert folder_names == sorted(folder_names)


class TestSizeLabels:
    """Test the map size label mapping."""

    def test_known_sizes(self, tmp_path: Path) -> None:
        maps = tmp_path / "maps"
        maps.mkdir()
        m = maps / "Small"
        m.mkdir()
        (m / "Small_scenario.lua").write_text(
            "ScenarioInfo = { name = 'Small', size = {256, 256} }",
            encoding="utf-8",
        )
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = maps
            results = map_scanner.scan_all_maps()
        assert results[0].size_label == "10km"
