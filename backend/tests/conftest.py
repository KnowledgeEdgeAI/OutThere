from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from outthere.auth import create_invite
from outthere.main import create_app
from outthere.settings import Settings


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            sync_poll_seconds=0.05,
            maps_provider="disabled",
            _env_file=None,
        )
    )
    SQLModel.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        yield client


def login(client, name):
    invite = create_invite(client.app.state.engine)
    response = client.post(
        "/v1/auth/exchange",
        json={
            "invite_token": invite,
            "display_name": name,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def connect(client, token, cursor=0):
    return client.websocket_connect("/v1/ws"), {
        "type": "auth",
        "access_token": token,
        "cursor": cursor,
    }


def rpc(socket, name, payload=None, *, query=False, action_id=None):
    request_id = str(uuid4())
    socket.send_json(
        {
            "id": request_id,
            "type": "query" if query else "command",
            "name": name,
            "payload": payload or {},
            "action_id": None if query else action_id or str(uuid4()),
        }
    )
    while True:
        response = socket.receive_json()
        if response.get("id") == request_id:
            return response


def result(socket, name, payload=None, **kwargs):
    response = rpc(socket, name, payload, **kwargs)
    assert response["type"] == "result", response
    return response["data"]
