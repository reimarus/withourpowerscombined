"""Tests for launcher.map_scanner."""

import struct
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


# ---------------------------------------------------------------------------
# Helpers for .scmap test data
# ---------------------------------------------------------------------------


def _make_scmap(path: Path, width: int = 1, height: int = 1) -> None:
    """Write a minimal valid .scmap with a WxH DDS preview.

    Produces a file with the correct Map header, DDS header at offset 0x22,
    and enough uncompressed BGRA pixel data for the given dimensions.
    """
    # Map header: "Map\x1a" + version 2 + padding to reach offset 0x22
    map_header = b"Map\x1a"
    map_header += struct.pack("<I", 2)  # version 2
    map_header += b"\x00" * (_DDS_OFFSET - len(map_header))  # pad to 0x22

    # DDS header (128 bytes total: 4 magic + 124 header)
    dds_header = b"DDS "
    dds_header += struct.pack("<I", 124)  # dwSize
    dds_header += struct.pack("<I", 0x1007)  # dwFlags
    dds_header += struct.pack("<I", height)  # dwHeight
    dds_header += struct.pack("<I", width)  # dwWidth
    dds_header += struct.pack("<I", width * 4)  # dwPitchOrLinearSize
    dds_header += b"\x00" * 4  # dwDepth
    dds_header += b"\x00" * 4  # dwMipMapCount
    dds_header += b"\x00" * 44  # dwReserved1[11]
    # DDPIXELFORMAT (32 bytes)
    dds_header += struct.pack("<I", 32)  # dwSize
    dds_header += struct.pack("<I", 0x41)  # dwFlags (DDPF_RGB | DDPF_ALPHAPIXELS)
    dds_header += b"\x00" * 4  # dwFourCC
    dds_header += struct.pack("<I", 32)  # dwRGBBitCount
    dds_header += struct.pack("<I", 0x00FF0000)  # R mask
    dds_header += struct.pack("<I", 0x0000FF00)  # G mask
    dds_header += struct.pack("<I", 0x000000FF)  # B mask
    dds_header += struct.pack("<I", 0xFF000000)  # A mask
    # dwCaps
    dds_header += struct.pack("<I", 0x1000)  # dwCaps (DDSCAPS_TEXTURE)
    dds_header += b"\x00" * 16  # dwCaps2-4 + dwReserved2

    # Pixel data: BGRA8888
    pixel_data = bytes([0x47, 0x85, 0x76, 0xFF]) * (width * height)

    path.write_bytes(map_header + dds_header + pixel_data)


_DDS_OFFSET = 0x22


# ---------------------------------------------------------------------------
# parse_scenario
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# scan_all_maps
# ---------------------------------------------------------------------------


class TestScanAllMaps:
    """Tests for scan_all_maps()."""

    def test_finds_valid_maps(self, maps_dir: Path, tmp_path: Path) -> None:
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = maps_dir
            mock_config.WOPC_USERMAPS = tmp_path / "usermaps_empty"
            results = map_scanner.scan_all_maps()

        # Should find Setons and TestMap but not EmptyFolder
        names = [m.folder_name for m in results]
        assert "Setons Clutch" in names
        assert "TestMap" in names
        assert "EmptyFolder" not in names

    def test_returns_empty_if_no_dir(self, tmp_path: Path) -> None:
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = tmp_path / "nonexistent"
            mock_config.WOPC_USERMAPS = tmp_path / "nonexistent2"
            results = map_scanner.scan_all_maps()
        assert results == []

    def test_results_sorted_by_folder(self, maps_dir: Path, tmp_path: Path) -> None:
        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = maps_dir
            mock_config.WOPC_USERMAPS = tmp_path / "usermaps_empty"
            results = map_scanner.scan_all_maps()
        folder_names = [m.folder_name for m in results]
        assert folder_names == sorted(folder_names)

    def test_scan_includes_usermaps(self, tmp_path: Path) -> None:
        maps = tmp_path / "maps"
        maps.mkdir()
        m1 = maps / "MapA"
        m1.mkdir()
        (m1 / "MapA_scenario.lua").write_text("ScenarioInfo = { name = 'Map A' }", encoding="utf-8")

        usermaps = tmp_path / "usermaps"
        usermaps.mkdir()
        m2 = usermaps / "MapB"
        m2.mkdir()
        (m2 / "MapB_scenario.lua").write_text("ScenarioInfo = { name = 'Map B' }", encoding="utf-8")

        with patch("launcher.map_scanner.config") as mock_config:
            mock_config.WOPC_MAPS = maps
            mock_config.WOPC_USERMAPS = usermaps
            results = map_scanner.scan_all_maps()

        names = [m.folder_name for m in results]
        assert "MapA" in names
        assert "MapB" in names


# ---------------------------------------------------------------------------
# Size labels
# ---------------------------------------------------------------------------


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
            mock_config.WOPC_USERMAPS = tmp_path / "usermaps_empty"
            results = map_scanner.scan_all_maps()
        assert results[0].size_label == "10km"


# ---------------------------------------------------------------------------
# Preview path (existing file detection)
# ---------------------------------------------------------------------------


class TestPreviewPath:
    """Tests for preview image detection in parse_scenario."""

    def test_finds_png_preview(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "scmp_007"
        map_dir.mkdir()
        scenario = map_dir / "scmp_007_scenario.lua"
        scenario.write_text("ScenarioInfo = { name = 'Setons' }", encoding="utf-8")
        preview = map_dir / "scmp_007_preview.png"
        preview.write_bytes(b"PNG_FAKE_DATA")

        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.preview_path == preview

    def test_finds_jpg_preview(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "mymap"
        map_dir.mkdir()
        scenario = map_dir / "mymap_scenario.lua"
        scenario.write_text("ScenarioInfo = { name = 'My Map' }", encoding="utf-8")
        preview = map_dir / "mymap_preview.jpg"
        preview.write_bytes(b"JPEG_FAKE_DATA")

        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.preview_path == preview

    def test_no_preview_when_absent_and_no_scmap(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "nopreview"
        map_dir.mkdir()
        scenario = map_dir / "nopreview_scenario.lua"
        scenario.write_text("ScenarioInfo = { name = 'No Preview Map' }", encoding="utf-8")

        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.preview_path is None

    def test_png_preferred_over_jpg(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "both"
        map_dir.mkdir()
        scenario = map_dir / "both_scenario.lua"
        scenario.write_text("ScenarioInfo = { name = 'Both' }", encoding="utf-8")
        png = map_dir / "both_preview.png"
        png.write_bytes(b"PNG_DATA")
        jpg = map_dir / "both_preview.jpg"
        jpg.write_bytes(b"JPEG_DATA")

        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.preview_path == png  # PNG takes priority


# ---------------------------------------------------------------------------
# .scmap DDS preview extraction
# ---------------------------------------------------------------------------


class TestScmapPreviewExtraction:
    """Tests for _extract_scmap_preview()."""

    def test_extracts_dds_from_valid_scmap(self, tmp_path: Path) -> None:
        pytest.importorskip("PIL")
        map_dir = tmp_path / "TestMap"
        map_dir.mkdir()
        _make_scmap(map_dir / "TestMap.scmap", width=2, height=2)

        result = map_scanner._extract_scmap_preview(map_dir, "TestMap")

        assert result is not None
        assert result.name == "TestMap_preview.png"
        assert result.exists()
        assert result.stat().st_size > 0

    def test_returns_none_for_missing_scmap(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "NoScmap"
        map_dir.mkdir()

        result = map_scanner._extract_scmap_preview(map_dir, "NoScmap")
        assert result is None

    def test_returns_none_for_invalid_magic(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "BadMagic"
        map_dir.mkdir()
        scmap = map_dir / "BadMagic.scmap"
        scmap.write_bytes(b"NOTAMAP" + b"\x00" * 300)

        result = map_scanner._extract_scmap_preview(map_dir, "BadMagic")
        assert result is None

    def test_returns_none_for_invalid_dds_magic(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "BadDDS"
        map_dir.mkdir()
        scmap = map_dir / "BadDDS.scmap"
        # Valid map header but garbage at DDS offset
        data = b"Map\x1a" + struct.pack("<I", 2) + b"\x00" * 0x1A + b"NOTDDS" + b"\x00" * 300
        scmap.write_bytes(data)

        result = map_scanner._extract_scmap_preview(map_dir, "BadDDS")
        assert result is None

    def test_returns_none_for_truncated_file(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "Truncated"
        map_dir.mkdir()
        scmap = map_dir / "Truncated.scmap"
        # Valid headers but pixel data is too short
        data = b"Map\x1a" + struct.pack("<I", 2) + b"\x00" * 0x1A
        data += b"DDS " + struct.pack("<I", 124) + struct.pack("<I", 0x1007)
        data += struct.pack("<II", 256, 256)  # height, width
        data += b"\x00" * 50  # not enough data
        scmap.write_bytes(data)

        result = map_scanner._extract_scmap_preview(map_dir, "Truncated")
        assert result is None

    def test_returns_none_for_zero_dimensions(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "ZeroDim"
        map_dir.mkdir()
        scmap = map_dir / "ZeroDim.scmap"
        # Valid map header, valid DDS magic, but 0x0 dimensions
        data = b"Map\x1a" + struct.pack("<I", 2) + b"\x00" * 0x1A
        data += b"DDS " + struct.pack("<I", 124) + struct.pack("<I", 0x1007)
        data += struct.pack("<II", 0, 0)  # height=0, width=0
        data += b"\x00" * 200
        scmap.write_bytes(data)

        result = map_scanner._extract_scmap_preview(map_dir, "ZeroDim")
        assert result is None

    def test_returns_none_when_pil_unavailable(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "NoPil"
        map_dir.mkdir()
        _make_scmap(map_dir / "NoPil.scmap")

        with patch.object(map_scanner, "_PIL_AVAILABLE", False):
            result = map_scanner._extract_scmap_preview(map_dir, "NoPil")
        assert result is None

    def test_skips_extraction_when_preview_exists(self, tmp_path: Path) -> None:
        map_dir = tmp_path / "HasPreview"
        map_dir.mkdir()
        scenario = map_dir / "HasPreview_scenario.lua"
        scenario.write_text("ScenarioInfo = { name = 'Has Preview' }", encoding="utf-8")
        preview = map_dir / "HasPreview_preview.png"
        preview.write_bytes(b"EXISTING_PNG")
        _make_scmap(map_dir / "HasPreview.scmap")

        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        # Should use existing preview, not extract from .scmap
        assert info.preview_path == preview
        assert info.preview_path.read_bytes() == b"EXISTING_PNG"

    def test_parse_scenario_uses_scmap_fallback(self, tmp_path: Path) -> None:
        pytest.importorskip("PIL")
        map_dir = tmp_path / "ScmapOnly"
        map_dir.mkdir()
        scenario = map_dir / "ScmapOnly_scenario.lua"
        scenario.write_text("ScenarioInfo = { name = 'Scmap Only' }", encoding="utf-8")
        _make_scmap(map_dir / "ScmapOnly.scmap", width=2, height=2)

        info = map_scanner.parse_scenario(scenario)
        assert info is not None
        assert info.preview_path is not None
        assert info.preview_path.name == "ScmapOnly_preview.png"
        assert info.preview_path.exists()
