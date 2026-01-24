import pytest

from study_agent_acp import server as acp_server
from study_agent_acp.mcp_client import StdioMCPClient


@pytest.mark.acp
def test_acp_shutdown_closes_mcp_client():
    class FakeServer:
        def serve_forever(self) -> None:
            raise RuntimeError("stop")

    class FakeMCPClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    fake_server = FakeServer()
    fake_client = FakeMCPClient()

    try:
        acp_server._serve(fake_server, fake_client)
    except RuntimeError:
        pass

    assert fake_client.closed is True


@pytest.mark.acp
def test_mcp_health_check_success():
    class Portal:
        def call(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    class Client:
        def __init__(self):
            self._portal = Portal()
            self._session = True

        def _ensure_session(self):
            return None

        def _ping(self):
            return {"ok": True}

        health_check = StdioMCPClient.health_check

    client = Client()
    assert client.health_check() == {"ok": True}
