"""Tests for the file transfer module."""

from __future__ import annotations

import base64
from pathlib import Path

from launcher.file_transfer import (
    build_file_manifest,
    format_size,
    iter_file_chunks,
    total_transfer_size,
    verify_file,
    write_chunk_to_disk,
)


class TestBuildFileManifest:
    """Test build_file_manifest() scans a directory tree."""

    def test_single_file(self, tmp_path: Path) -> None:
        """Manifest for a directory with one file."""
        (tmp_path / "test.txt").write_text("hello world")
        manifest = build_file_manifest(tmp_path)
        assert len(manifest) == 1
        assert manifest[0]["path"] == "test.txt"
        assert manifest[0]["size"] == 11
        assert len(manifest[0]["sha256"]) == 64  # hex digest length

    def test_nested_files(self, tmp_path: Path) -> None:
        """Manifest includes files in subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.txt").write_text("aaa")
        (sub / "b.txt").write_text("bbb")
        manifest = build_file_manifest(tmp_path)
        paths = [m["path"] for m in manifest]
        assert "a.txt" in paths
        assert "sub/b.txt" in paths

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns empty manifest."""
        assert build_file_manifest(tmp_path) == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        """Non-existent directory returns empty manifest."""
        assert build_file_manifest(tmp_path / "nope") == []


class TestIterFileChunks:
    """Test iter_file_chunks() splits files into base64-encoded chunks."""

    def test_small_file_single_chunk(self, tmp_path: Path) -> None:
        """Small file fits in a single chunk."""
        (tmp_path / "small.bin").write_bytes(b"hello")
        chunks = iter_file_chunks(tmp_path, "small.bin")
        assert len(chunks) == 1
        assert chunks[0]["index"] == 0
        assert chunks[0]["total"] == 1
        assert base64.b64decode(chunks[0]["data"]) == b"hello"

    def test_large_file_multiple_chunks(self, tmp_path: Path) -> None:
        """Large file is split into multiple chunks."""
        data = b"x" * 200_000  # ~200 KB
        (tmp_path / "big.bin").write_bytes(data)
        chunks = iter_file_chunks(tmp_path, "big.bin", chunk_size=64 * 1024)
        # 200KB / 64KB = ~3.1 → 4 chunks
        assert len(chunks) == 4
        # Reassemble
        reassembled = b""
        for c in chunks:
            reassembled += base64.b64decode(c["data"])
        assert reassembled == data

    def test_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns empty list."""
        assert iter_file_chunks(tmp_path, "nope.bin") == []


class TestWriteChunkToDisk:
    """Test write_chunk_to_disk() reconstructs files from chunks."""

    def test_single_chunk(self, tmp_path: Path) -> None:
        """Single chunk creates complete file."""
        data = b"test data"
        b64 = base64.b64encode(data).decode()
        path = write_chunk_to_disk(tmp_path, "out.bin", 0, 1, b64)
        assert path.read_bytes() == data

    def test_multi_chunk_append(self, tmp_path: Path) -> None:
        """Multiple chunks are appended in order."""
        part1 = base64.b64encode(b"AAAA").decode()
        part2 = base64.b64encode(b"BBBB").decode()
        write_chunk_to_disk(tmp_path, "out.bin", 0, 2, part1)
        path = write_chunk_to_disk(tmp_path, "out.bin", 1, 2, part2)
        assert path.read_bytes() == b"AAAABBBB"

    def test_creates_subdirs(self, tmp_path: Path) -> None:
        """Parent directories are created as needed."""
        b64 = base64.b64encode(b"data").decode()
        path = write_chunk_to_disk(tmp_path, "sub/dir/file.txt", 0, 1, b64)
        assert path.exists()
        assert path.read_bytes() == b"data"


class TestVerifyFile:
    """Test verify_file() checks SHA256 hashes."""

    def test_correct_hash(self, tmp_path: Path) -> None:
        """Correct hash returns True."""
        import hashlib

        data = b"verify me"
        (tmp_path / "f.bin").write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        assert verify_file(tmp_path, "f.bin", sha) is True

    def test_wrong_hash(self, tmp_path: Path) -> None:
        """Wrong hash returns False."""
        (tmp_path / "f.bin").write_bytes(b"data")
        assert verify_file(tmp_path, "f.bin", "0" * 64) is False

    def test_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns False."""
        assert verify_file(tmp_path, "nope.bin", "0" * 64) is False


class TestRoundTrip:
    """End-to-end: build manifest, chunk, transfer, verify."""

    def test_full_transfer(self, tmp_path: Path) -> None:
        """Simulate a full map transfer: scan → chunk → write → verify."""
        src = tmp_path / "src_map"
        dst = tmp_path / "dst_map"
        src.mkdir()

        # Create test map files
        (src / "scenario.lua").write_text("-- scenario")
        (src / "script.lua").write_text("-- script")
        sub = src / "textures"
        sub.mkdir()
        (sub / "heightmap.dds").write_bytes(b"\x00" * 1024)

        # Build manifest
        manifest = build_file_manifest(src)
        assert len(manifest) == 3

        # Transfer all files via chunks
        for f_info in manifest:
            chunks = iter_file_chunks(src, f_info["path"])
            for chunk in chunks:
                write_chunk_to_disk(
                    dst, chunk["path"], chunk["index"], chunk["total"], chunk["data"]
                )

        # Verify all files
        for f_info in manifest:
            assert verify_file(dst, f_info["path"], f_info["sha256"])


class TestHelpers:
    """Test utility functions."""

    def test_total_transfer_size(self) -> None:
        files = [{"size": 100}, {"size": 200}, {"size": 50}]
        assert total_transfer_size(files) == 350

    def test_format_size_bytes(self) -> None:
        assert format_size(500) == "500 B"

    def test_format_size_kb(self) -> None:
        assert format_size(2048) == "2.0 KB"

    def test_format_size_mb(self) -> None:
        assert format_size(5 * 1024 * 1024) == "5.0 MB"
