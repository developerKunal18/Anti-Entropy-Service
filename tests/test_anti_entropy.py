import pytest
import app as module

@pytest.fixture(autouse=True)
def reset_store():
    module.store = module.AntiEntropy()
    yield

@pytest.fixture
def client():
    module.app.config["TESTING"] = True
    return module.app.test_client()

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"

def test_compare_detects_missing_record(client):
    client.put("/api/state", json={"node_id": "node-1", "key": "status", "value": "online"})
    r = client.get("/api/compare/node-1/node-2")
    assert r.status_code == 200
    assert r.get_json()["missing_from_b"] == ["status"]

def test_sync_repairs_missing_record(client):
    client.put("/api/state", json={"node_id": "node-1", "key": "status", "value": "online"})
    r = client.post("/api/sync/node-1/node-2")
    assert r.status_code == 200
    state = client.get("/api/state/node-2").get_json()["state"]
    assert state["status"]["value"] == "online"

def test_newer_record_wins(client):
    client.put("/api/state", json={"node_id": "node-1", "key": "mode", "value": "old"})
    client.put("/api/state", json={"node_id": "node-2", "key": "mode", "value": "new"})
    assert client.post("/api/sync/node-1/node-2").status_code == 200
    a = client.get("/api/state/node-1").get_json()["state"]
    b = client.get("/api/state/node-2").get_json()["state"]
    assert a["mode"]["value"] == "new"
    assert b["mode"]["value"] == "new"

def test_replicas_converge(client):
    client.put("/api/state", json={"node_id": "node-1", "key": "x", "value": 1})
    client.put("/api/state", json={"node_id": "node-2", "key": "y", "value": 2})
    client.post("/api/sync/node-1/node-2")
    result = client.get("/api/compare/node-1/node-2").get_json()
    assert result["missing_from_a"] == []
    assert result["missing_from_b"] == []
    assert result["stale_on_a"] == []
    assert result["stale_on_b"] == []
    assert result["equal"] == ["x", "y"]
