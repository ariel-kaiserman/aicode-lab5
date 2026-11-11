import http.client
import json
import runpy
import threading
from collections.abc import Iterator
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest

from server import make_server

SERVER_SCRIPT = Path(__file__).parent.parent / "server.py"


@pytest.fixture
def server() -> Iterator[HTTPServer]:
    """A server on a free port, serving from a background thread."""
    instance = make_server(0)
    # A short poll interval keeps shutdown, and so each test, fast.
    thread = threading.Thread(
        target=instance.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()


def call(
    server: HTTPServer,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type", ""), response.read()
    finally:
        connection.close()


def act(server: HTTPServer, action: object) -> tuple[int, Any]:
    status, content_type, body = call(
        server, "POST", "/api/action", json.dumps(action).encode()
    )
    assert content_type == "application/json"
    return status, json.loads(body)


def test_state_starts_with_a_new_game(server: HTTPServer) -> None:
    status, content_type, body = call(server, "GET", "/api/state")
    assert status == 200 and content_type == "application/json"
    state = json.loads(body)
    assert state["turn"] == "w" and state["moves"] == []
    assert len(state["board"]) == 32


@pytest.mark.parametrize(
    "path,content_type,name",
    [
        ("/", "text/html; charset=utf-8", "index.html"),
        ("/app.js", "text/javascript; charset=utf-8", "app.js"),
        ("/style.css", "text/css; charset=utf-8", "style.css"),
    ],
)
def test_static_files(
    server: HTTPServer, path: str, content_type: str, name: str
) -> None:
    status, served_type, body = call(server, "GET", path)
    assert status == 200 and served_type == content_type
    assert body == (SERVER_SCRIPT.parent / "static" / name).read_bytes()


@pytest.mark.parametrize("method,path", [("GET", "/missing"), ("POST", "/api/state")])
def test_unknown_paths(server: HTTPServer, method: str, path: str) -> None:
    status, _, body = call(server, method, path, b"{}" if method == "POST" else None)
    assert status == 404 and json.loads(body) == {"error": "Not found"}


def test_actions_change_the_shared_game(server: HTTPServer) -> None:
    status, state = act(server, {"action": "move", "source": "e2", "target": "e4"})
    assert status == 200 and state["moves"] == ["e2-e4"]
    status, state = act(server, {"action": "undo"})
    assert status == 200 and state["moves"] == [] and state["can_redo"]
    status, state = act(server, {"action": "redo"})
    assert state["moves"] == ["e2-e4"]
    _, _, body = call(server, "GET", "/api/state")
    assert json.loads(body)["moves"] == ["e2-e4"]


@pytest.mark.parametrize(
    "action,error",
    [
        ({"action": "move", "source": "e2", "target": "e5"}, "not allowed"),
        ({"action": "fly"}, "Unknown action"),
        (["move"], "Expected an action object"),
    ],
)
def test_bad_actions_are_client_errors(
    server: HTTPServer, action: object, error: str
) -> None:
    status, result = act(server, action)
    assert status == 400 and error in result["error"]


@pytest.mark.parametrize(
    "body,headers",
    [
        (b"not json", {}),
        (b"", {}),
        (b"{}", {"Content-Length": "2000000"}),
    ],
)
def test_malformed_requests_are_client_errors(
    server: HTTPServer, body: bytes, headers: dict[str, str]
) -> None:
    status, _, response = call(server, "POST", "/api/action", body, headers)
    assert status == 400 and "error" in json.loads(response)


def test_running_the_script_serves_until_interrupted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted(self: HTTPServer) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(HTTPServer, "serve_forever", interrupted)
    monkeypatch.setattr("sys.argv", ["server.py", "--port", "0"])
    runpy.run_path(str(SERVER_SCRIPT), run_name="__main__")
    assert capsys.readouterr().out.startswith("Open http://127.0.0.1:")
