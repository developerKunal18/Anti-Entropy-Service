# Anti Entropy Service

A small Flask service demonstrating anti-entropy synchronization between distributed replicas.

## Features
- Register/remove replicas
- Versioned key/value records
- Compare two replicas
- Repair missing or stale records
- Track synchronization rounds
- Thread-safe in-memory state
- Health endpoint
- Pytest tests

## Run
```bash
pip install -r requirements.txt
python app.py
```

## API
- `POST /api/nodes`
- `GET /api/nodes`
- `DELETE /api/nodes/<node_id>`
- `PUT /api/state`
- `GET /api/state/<node_id>`
- `GET /api/compare/<node_a>/<node_b>`
- `POST /api/sync/<node_a>/<node_b>`
- `GET /api/stats`
- `GET /health`

## Concepts
Anti-entropy, replica synchronization, eventual consistency, state reconciliation, versioned records, conflict resolution, distributed systems.
