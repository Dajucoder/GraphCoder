"""Web transport tests with an in-memory fake bridge."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.server import create_app


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def request(self, method: str, params: dict):
        self.calls.append((method, params))
        if method == "threads/list":
            return {"threads": [{"id": "t1", "title": "测试会话"}]}
        if method == "initialize":
            return {"protocolVersion": "1.0", "defaults": {"model": "m"}}
        if method == "nope":
            raise RuntimeError("未知方法: nope")
        return {"ok": True}

    async def subscribe(self):
        import asyncio

        return asyncio.Queue()

    async def unsubscribe(self, queue) -> None:
        pass


def _client() -> TestClient:
    bridge = FakeBridge()
    app = create_app(workspace=__import__("pathlib").Path.cwd(), bridge=bridge)  # type: ignore[arg-type]
    return TestClient(app)


def test_health() -> None:
    resp = _client().get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["version"] == "2.0.0"


def test_rpc_bridge() -> None:
    client = _client()
    resp = client.post("/api/v1/rpc", json={"method": "threads/list", "params": {}})
    assert resp.status_code == 200
    assert resp.json()["result"]["threads"][0]["title"] == "测试会话"


def test_rpc_error_surface() -> None:
    client = _client()
    resp = client.post("/api/v1/rpc", json={"method": "nope"})
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_v1_session_adapter() -> None:
    client = _client()
    resp = client.get("/api/v1/sessions")
    assert resp.json()["threads"][0]["id"] == "t1"
    resp2 = client.post("/api/v1/sessions", json={"title": "x"})
    assert resp2.json() == {"ok": True}
