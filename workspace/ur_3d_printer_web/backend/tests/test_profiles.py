"""Material / process profiles: store and endpoints."""

import pytest

from backend import deps
from backend.profiles import ProfileStore


@pytest.fixture
def profiles(tmp_path, monkeypatch):
    store = ProfileStore(str(tmp_path / "profiles.json"))
    monkeypatch.setattr(deps, "profiles", store)
    return store


def test_builtins_are_listed_first(profiles):
    items = profiles.list()
    assert items[0]["builtin"] is True
    assert all("settings" in p for p in items)


def test_upsert_persists_and_filters_unknown_keys(tmp_path, profiles):
    p = profiles.upsert("Mi PETG", {"material": "petg", "layer_height": 0.3, "junk": True})
    assert p["id"] == "mi-petg" and p["builtin"] is False
    assert p["settings"] == {"material": "petg", "layer_height": 0.3}
    again = ProfileStore(str(tmp_path / "profiles.json"))
    assert again.get("mi-petg")["name"] == "Mi PETG"


def test_saving_over_a_builtin_makes_a_copy(profiles):
    p = profiles.upsert("PLA copy", {"material": "pla"}, profile_id="pla-standard")
    assert p["id"] != "pla-standard"
    assert profiles.get("pla-standard")["builtin"] is True


def test_endpoints(client, profiles):
    assert client.get("/api/profiles").status_code == 200
    res = client.put("/api/profiles", json={"name": "Clay fast", "settings": {"material": "clay", "print_speed": 2500}})
    assert res.status_code == 200, res.text
    pid = res.json()["id"]
    # Update by id keeps the id.
    res = client.put("/api/profiles", json={"id": pid, "name": "Clay faster", "settings": {"print_speed": 3000}})
    assert res.json()["id"] == pid and res.json()["name"] == "Clay faster"
    assert client.put("/api/profiles", json={"id": "nope", "name": "x", "settings": {}}).status_code == 404
    assert client.put("/api/profiles", json={"id": "pla-standard", "name": "x", "settings": {}}).status_code == 403
    assert client.delete("/api/profiles/pla-standard").status_code == 403
    assert client.delete(f"/api/profiles/{pid}").status_code == 200
    assert client.delete(f"/api/profiles/{pid}").status_code == 404


def test_name_is_required(client, profiles):
    assert client.put("/api/profiles", json={"name": "", "settings": {}}).status_code == 422
