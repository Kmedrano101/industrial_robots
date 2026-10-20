"""STL upload: validation, streaming size cap, path confinement."""

import struct

import numpy as np
import pytest

from backend.config import settings


def binary_stl(triangles: int = 2) -> bytes:
    """A valid binary STL: `triangles` unit triangles stacked along Z."""
    body = bytearray(b"\0" * 80 + struct.pack("<I", triangles))
    for i in range(triangles):
        z = float(i)
        verts = [(0, 0, z), (10, 0, z), (0, 20, z)]
        body += struct.pack("<3f", 0, 0, 1)
        for v in verts:
            body += struct.pack("<3f", *v)
        body += struct.pack("<H", 0)
    return bytes(body)


def post(client, name: str, data: bytes):
    return client.post("/api/upload", files={"file": (name, data, "application/octet-stream")})


def test_valid_binary_stl_is_stored_with_metadata(client, upload_dir):
    res = post(client, "part.stl", binary_stl(3))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["filename"] == "part.stl"
    assert body["triangle_count"] == 3
    assert body["bounding_box"]["x_max"] == pytest.approx(10.0)
    assert body["bounding_box"]["z_max"] == pytest.approx(2.0)
    assert (upload_dir / body["filepath"].split("/")[-1]).is_file()
    assert not list(upload_dir.glob("*.part"))


def test_ascii_stl_is_accepted(client, upload_dir):
    data = b"solid x\n" + b" " * 100 + b"\nendsolid x\n"
    assert post(client, "a.stl", data).status_code == 200


def test_wrong_extension_is_rejected(client, upload_dir):
    res = post(client, "model.obj", binary_stl())
    assert res.status_code == 400
    assert list(upload_dir.iterdir()) == []


def test_too_small_file_is_rejected(client, upload_dir):
    assert post(client, "x.stl", b"\0" * 50).status_code == 400
    assert list(upload_dir.iterdir()) == []


def test_truncated_binary_stl_is_rejected(client, upload_dir):
    data = binary_stl(4)[:-30]
    res = post(client, "x.stl", data)
    assert res.status_code == 400
    assert "triangle count" in res.json()["detail"]
    assert list(upload_dir.iterdir()) == []


def test_oversize_upload_is_rejected_and_cleaned_up(client, upload_dir, monkeypatch):
    monkeypatch.setattr("backend.routes.upload.MAX_SIZE", 1024)
    res = post(client, "big.stl", b"\0" * 4096)
    assert res.status_code == 400
    assert "too large" in res.json()["detail"]
    assert list(upload_dir.iterdir()) == []


def test_filename_is_sanitised(client, upload_dir):
    res = post(client, "../../etc/pass wd;.stl", binary_stl())
    assert res.status_code == 200
    assert res.json()["filename"] == "pass_wd_.stl"
    assert all(p.parent == upload_dir for p in upload_dir.iterdir())


def test_preview_refuses_paths_outside_upload_dir(client, upload_dir, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.stl"
    outside.write_bytes(binary_stl())
    assert client.get("/api/stl-preview", params={"filepath": str(outside)}).status_code == 403
    # A sibling directory sharing the prefix must not pass either.
    sibling = str(upload_dir) + "_x/secret.stl"
    assert client.get("/api/stl-preview", params={"filepath": sibling}).status_code == 403


def test_slice_refuses_paths_outside_upload_dir(client, upload_dir, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "m.stl"
    outside.write_bytes(binary_stl())
    res = client.post("/api/slice", json={"stl_filepath": str(outside)})
    assert res.status_code == 403


def test_slice_missing_file_is_404(client, upload_dir):
    res = client.post("/api/slice", json={"stl_filepath": str(upload_dir / "nope.stl")})
    assert res.status_code == 404
