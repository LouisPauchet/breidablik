import tarfile

import pytest

from scripts.passenger_update import extract


def _make_archive(tmp_path, name: str, arcname: str, content: bytes = b"hello") -> None:
    src = tmp_path / "payload.txt"
    src.write_bytes(content)
    archive_path = tmp_path / name
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(src, arcname=arcname)


def test_extract_normal_archive_lands_inside_dest(tmp_path):
    _make_archive(tmp_path, "good.tar.gz", "breidablik/app/main.py")
    dest = tmp_path / "dest"
    dest.mkdir()

    extract(tmp_path / "good.tar.gz", dest)

    assert (dest / "breidablik" / "app" / "main.py").read_bytes() == b"hello"


def test_extract_rejects_path_traversal_member(tmp_path):
    _make_archive(tmp_path, "evil.tar.gz", "../../../../tmp/evil.txt")
    dest = tmp_path / "dest"
    dest.mkdir()

    with pytest.raises(Exception):
        extract(tmp_path / "evil.tar.gz", dest)

    assert not (tmp_path / "tmp" / "evil.txt").exists()


def test_extract_hard_aborts_when_data_filter_unavailable(tmp_path, monkeypatch):
    import scripts.passenger_update as module

    _make_archive(tmp_path, "good.tar.gz", "breidablik/app/main.py")
    dest = tmp_path / "dest"
    dest.mkdir()

    monkeypatch.delattr(module.tarfile, "data_filter", raising=False)

    with pytest.raises(RuntimeError, match="PEP 706"):
        extract(tmp_path / "good.tar.gz", dest)

    # Nothing should have been written — this must be a hard abort, not a silent fallback.
    assert list(dest.iterdir()) == []
