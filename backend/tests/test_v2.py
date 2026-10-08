from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, select

from outthere import sessions, v2
from outthere.db import transaction
from outthere.errors import AppError
from outthere.main import create_app
from outthere.models import ActionReceipt, AuthOperation, AuthSession, Device, User, now
from outthere.settings import Settings
from outthere.v2_contracts import Frame, Login, Renewal


@pytest.fixture
def connected(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'v2.db'}",
        auth_mode="unverified_phone",
        auth_retry_key=Fernet.generate_key().decode(),
        sync_poll_seconds=0.05,
        _env_file=None,
    )
    app = create_app(settings)
    SQLModel.metadata.create_all(app.state.engine)
    with TestClient(app) as client:
        yield client, settings


def frame(name, payload=None, *, action_id=None, issued_at=None):
    return Frame(
        v=2,
        id=uuid4(),
        type=v2.CONTRACTS[name][0],
        name=name,
        payload=payload or {},
        action_id=action_id,
        issued_at=issued_at,
    )


def rpc(socket, request):
    socket.send_json(request.model_dump(mode="json"))
    while True:
        response = socket.receive_json()
        if response.get("id") == str(request.id):
            return response


def login(socket, installation=None):
    response = rpc(
        socket,
        frame(
            "auth.login",
            {
                "phone": "+91 98765 43210",
                "installation_id": str(installation or uuid4()),
                "platform": "web",
                "name": "Divya",
            },
        ),
    )
    assert response["type"] == "result", response
    return response["data"]


def test_devices_profile_replay_and_revocation(connected):
    client, _ = connected
    with client.websocket_connect("/v2/ws") as a, client.websocket_connect("/v2/ws") as b:
        first, second = login(a), login(b)
        assert first["user_id"] == second["user_id"]
        assert first["device_id"] != second["device_id"]
        assert len(rpc(a, frame("device.list"))["data"]["items"]) == 2
        intent = frame(
            "profile.update",
            {"name": "D", "expected_version": 1},
            action_id=uuid4(),
            issued_at=datetime.now(UTC),
        )
        result = rpc(a, intent)
        assert result["data"]["version"] == 2
        assert rpc(a, intent) == result
        assert rpc(b, frame("profile.get"))["data"]["name"] == "D"
        changed = intent.model_copy(update={"payload": {"name": "Other", "expected_version": 1}})
        assert rpc(a, changed)["error"]["code"] == "action_conflict"
        stale = frame(
            "profile.update",
            {"name": "Old", "expected_version": 1},
            action_id=uuid4(),
            issued_at=datetime.now(UTC),
        )
        assert rpc(b, stale)["error"]["code"] == "version_conflict"
        revoke = frame(
            "device.revoke",
            {"device_id": second["device_id"]},
            action_id=uuid4(),
            issued_at=datetime.now(UTC),
        )
        assert rpc(a, revoke)["data"]["revoked"]
        while True:
            event = b.receive_json()
            if event["type"] == "error":
                assert event["error"]["code"] == "unauthenticated"
                break
    with transaction(client.app.state.engine) as db:
        assert len(db.exec(select(User)).all()) == 1
        assert len(db.exec(select(Device)).all()) == 2


def test_lost_refresh_response_and_encrypted_retry(connected):
    client, settings = connected
    engine = client.app.state.engine
    with client.websocket_connect("/v2/ws") as socket:
        pair = login(socket)
    data = Renewal(
        refresh_token=pair["refresh_token"], device_id=pair["device_id"], renewal_id=uuid4()
    )
    with transaction(engine, write=True) as db:
        result = sessions.renew(db, settings, data)
    with client.websocket_connect("/v2/ws") as socket:
        assert rpc(socket, frame("auth.refresh", data.model_dump(mode="json")))["data"] == (
            result | {"capabilities": list(v2.CONTRACTS)}
        )
    with transaction(engine) as db:
        operation = db.exec(select(AuthOperation)).one()
        record = db.exec(select(AuthSession)).one()
        assert result["refresh_token"] not in operation.encrypted_result
        assert result["access_token"] not in operation.encrypted_result
        assert record.refresh_hash != result["refresh_token"]
        with pytest.raises(AppError):
            sessions.authenticate(db, pair["access_token"], UUID(pair["device_id"]))
    with transaction(engine, write=True) as db:
        sessions.revoke(db, UUID(pair["user_id"]), UUID(pair["device_id"]))
    with transaction(engine, write=True) as db:
        with pytest.raises(AppError):
            sessions.renew(db, settings, data)


def test_concurrent_action_and_stale_action_without_receipt(connected):
    client, settings = connected
    engine = client.app.state.engine
    with client.websocket_connect("/v2/ws") as socket:
        pair = login(socket)
    request = frame(
        "profile.update",
        {"name": "Once", "expected_version": 1},
        action_id=uuid4(),
        issued_at=datetime.now(UTC),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                v2.handle, engine, settings, request, pair["access_token"], UUID(pair["device_id"])
            )
            for _ in range(2)
        ]
        assert futures[0].result() == futures[1].result()
    with transaction(engine, write=True) as db:
        db.delete(db.exec(select(ActionReceipt)).one())
    request = request.model_copy(update={"issued_at": datetime.now(UTC) - timedelta(days=31)})
    with pytest.raises(AppError, match="expired"):
        v2.handle(engine, settings, request, pair["access_token"], UUID(pair["device_id"]))
    with transaction(engine) as db:
        assert db.exec(select(User)).one().version == 2


def test_binding_validation_logout_and_relogin(connected):
    client, _ = connected
    installation = uuid4()
    with client.websocket_connect("/v2/ws") as socket:
        pair = login(socket, installation)
        invalid = frame(
            "profile.update",
            {"name": "X", "expected_version": 1, "phone": "secret"},
            action_id=uuid4(),
            issued_at=datetime.now(UTC),
        )
        response = rpc(socket, invalid)
        assert response["error"]["code"] == "invalid_input"
        assert "secret" not in str(response)
        assert rpc(socket, frame("auth.logout"))["data"]["signed_out"]
    with client.websocket_connect("/v2/ws") as socket:
        assert (
            rpc(
                socket,
                frame(
                    "auth.resume",
                    {"access_token": pair["access_token"], "device_id": pair["device_id"]},
                ),
            )["error"]["code"]
            == "unauthenticated"
        )
    with client.websocket_connect("/v2/ws") as socket:
        assert rpc(socket, frame("profile.get"))["error"]["code"] == "unauthenticated"
    with client.websocket_connect("/v2/ws") as socket:
        fresh = login(socket, installation)
    assert fresh["device_id"] == pair["device_id"]
    with transaction(client.app.state.engine) as db:
        with pytest.raises(AppError):
            sessions.authenticate(db, fresh["access_token"], uuid4())
    with pytest.raises(ValueError):
        Login(phone="9876543210", installation_id=uuid4(), platform="web")


def test_expired_renewal_and_expired_access(connected):
    client, settings = connected
    engine = client.app.state.engine
    with client.websocket_connect("/v2/ws") as socket:
        pair = login(socket)
    data = Renewal(
        refresh_token=pair["refresh_token"], device_id=pair["device_id"], renewal_id=uuid4()
    )
    with transaction(engine, write=True) as db:
        sessions.renew(db, settings, data)
        db.flush()
        db.exec(select(AuthOperation)).one().expires_at = now() - 1
    with transaction(engine) as db:
        with pytest.raises(AppError):
            sessions.renew(db, settings, data)


def test_phone_mode_is_explicit(client):
    with client.websocket_connect("/v2/ws") as socket:
        response = rpc(
            socket,
            frame(
                "auth.login",
                {
                    "phone": "+919876543210",
                    "installation_id": str(uuid4()),
                    "platform": "web",
                    "name": "D",
                },
            ),
        )
        assert response["error"]["code"] == "provider_unavailable"


def test_schema_file_matches_supported_contracts():
    import json
    from pathlib import Path

    assert json.loads(Path("docs/v2-contracts.json").read_text()) == v2.contract_schemas()


def test_invalid_envelopes_remain_correlated_and_v1_cannot_renew_v2(connected):
    client, _ = connected
    with client.websocket_connect("/v2/ws") as socket:
        pair = login(socket)
        request = frame("profile.get").model_dump(mode="json") | {"unexpected": "private"}
        socket.send_json(request)
        response = socket.receive_json()
        assert response["id"] == request["id"]
        assert response["error"]["code"] == "invalid_input"
        assert "private" not in str(response)
        assert (
            client.post(
                "/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/v1/auth/logout", headers={"Authorization": f"Bearer {pair['access_token']}"}
            ).status_code
            == 401
        )


def test_idle_worker_removes_expired_recovery_data(connected):
    from outthere.worker import run_once

    client, settings = connected
    engine = client.app.state.engine
    with client.websocket_connect("/v2/ws") as socket:
        pair = login(socket)
    data = Renewal(
        refresh_token=pair["refresh_token"], device_id=pair["device_id"], renewal_id=uuid4()
    )
    with transaction(engine, write=True) as db:
        sessions.renew(db, settings, data)
        db.flush()
        db.exec(select(AuthOperation)).one().expires_at = now() - 1
    assert not run_once(engine)
    with transaction(engine) as db:
        assert db.exec(select(AuthOperation)).all() == []
