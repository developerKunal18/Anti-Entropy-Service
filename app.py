from copy import deepcopy
from threading import RLock
from flask import Flask, jsonify, request

app = Flask(__name__)
LOCK = RLock()
DEFAULT_NODES = ("node-1", "node-2", "node-3")


class AntiEntropy:
    def __init__(self):
        self.nodes = {}
        self.sync_rounds = 0
        self.sync_counts = {}
        for node in DEFAULT_NODES:
            self.add_node(node)

    def add_node(self, node_id):
        if not node_id or len(node_id) > 64:
            raise ValueError("node_id must contain 1-64 characters")
        if node_id not in self.nodes:
            self.nodes[node_id] = {}
            self.sync_counts[node_id] = 0

    def remove_node(self, node_id):
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.sync_counts.pop(node_id, None)
            return True
        return False

    def write(self, node_id, key, value):
        if node_id not in self.nodes:
            raise KeyError("node not found")
        if not key or len(key) > 128:
            raise ValueError("key must contain 1-128 characters")
        old = self.nodes[node_id].get(key)
        version = old["version"] + 1 if old else 1
        record = {"value": value, "version": version, "origin": node_id}
        self.nodes[node_id][key] = record
        return deepcopy(record)

    @staticmethod
    def merge(target, incoming):
        changed = 0
        for key, record in incoming.items():
            current = target.get(key)
            if current is None or (record["version"], record["origin"]) > (
                current["version"], current["origin"]
            ):
                target[key] = deepcopy(record)
                changed += 1
        return changed

    def compare(self, node_a, node_b):
        if node_a not in self.nodes or node_b not in self.nodes:
            raise KeyError("node not found")
        a, b = self.nodes[node_a], self.nodes[node_b]
        result = {
            "node_a": node_a, "node_b": node_b,
            "missing_from_a": [], "missing_from_b": [],
            "stale_on_a": [], "stale_on_b": [], "equal": []
        }
        for key in sorted(set(a) | set(b)):
            if key not in a:
                result["missing_from_a"].append(key)
            elif key not in b:
                result["missing_from_b"].append(key)
            elif a[key] == b[key]:
                result["equal"].append(key)
            elif (a[key]["version"], a[key]["origin"]) > (b[key]["version"], b[key]["origin"]):
                result["stale_on_b"].append(key)
            else:
                result["stale_on_a"].append(key)
        return result

    def sync(self, node_a, node_b):
        if node_a not in self.nodes or node_b not in self.nodes:
            raise KeyError("node not found")
        if node_a == node_b:
            raise ValueError("nodes must be different")
        before = self.compare(node_a, node_b)
        state_a = deepcopy(self.nodes[node_a])
        state_b = deepcopy(self.nodes[node_b])
        changes_a = self.merge(self.nodes[node_a], state_b)
        changes_b = self.merge(self.nodes[node_b], state_a)
        changes_a += self.merge(self.nodes[node_a], self.nodes[node_b])
        changes_b += self.merge(self.nodes[node_b], self.nodes[node_a])
        self.sync_rounds += 1
        self.sync_counts[node_a] += 1
        self.sync_counts[node_b] += 1
        return {
            "round": self.sync_rounds,
            "changes_on_a": changes_a,
            "changes_on_b": changes_b,
            "before": before,
            "after": self.compare(node_a, node_b)
        }

    def stats(self):
        return {
            "nodes": len(self.nodes),
            "sync_rounds": self.sync_rounds,
            "sync_counts": dict(self.sync_counts),
            "records": sum(len(state) for state in self.nodes.values())
        }


store = AntiEntropy()

@app.get("/health")
def health():
    return jsonify({"status": "ok", "nodes": len(store.nodes)})

@app.get("/api/nodes")
def list_nodes():
    with LOCK:
        return jsonify({"nodes": sorted(store.nodes)})

@app.post("/api/nodes")
def add_node():
    body = request.get_json(silent=True) or {}
    node_id = str(body.get("node_id", "")).strip()
    try:
        with LOCK:
            if node_id in store.nodes:
                return jsonify({"error": "node already exists"}), 409
            store.add_node(node_id)
        return jsonify({"node_id": node_id, "created": True}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.delete("/api/nodes/<node_id>")
def remove_node(node_id):
    with LOCK:
        if not store.remove_node(node_id):
            return jsonify({"error": "node not found"}), 404
    return jsonify({"node_id": node_id, "removed": True})

@app.put("/api/state")
def write_state():
    body = request.get_json(silent=True) or {}
    node_id = str(body.get("node_id", "")).strip()
    key = str(body.get("key", "")).strip()
    if "value" not in body:
        return jsonify({"error": "value is required"}), 400
    try:
        with LOCK:
            record = store.write(node_id, key, body["value"])
        return jsonify({"node_id": node_id, "key": key, **record}), 201
    except KeyError:
        return jsonify({"error": "node not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.get("/api/state/<node_id>")
def get_state(node_id):
    with LOCK:
        if node_id not in store.nodes:
            return jsonify({"error": "node not found"}), 404
        return jsonify({"node_id": node_id, "state": deepcopy(store.nodes[node_id])})

@app.get("/api/compare/<node_a>/<node_b>")
def compare(node_a, node_b):
    try:
        with LOCK:
            return jsonify(store.compare(node_a, node_b))
    except KeyError:
        return jsonify({"error": "node not found"}), 404

@app.post("/api/sync/<node_a>/<node_b>")
def sync(node_a, node_b):
    try:
        with LOCK:
            return jsonify(store.sync(node_a, node_b))
    except KeyError:
        return jsonify({"error": "node not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

@app.get("/api/stats")
def stats():
    with LOCK:
        return jsonify(store.stats())

if __name__ == "__main__":
    app.run(debug=True)
