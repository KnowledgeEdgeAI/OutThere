from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from conftest import connect, login, result, rpc
from sqlmodel import select
from starlette.websockets import WebSocketDisconnect

from outthere import auth, service
from outthere.contracts import Envelope
from outthere.db import make_engine, transaction
from outthere.errors import AppError
from outthere.models import AuthSession, Change, Job, Message, Participant, Plan, Receipt, now
from outthere.worker import run_once


def plan_payload(circle_id=None):
    start = datetime.now(UTC) + timedelta(days=2)
    return {
        "title": "Badminton then coffee",
        "circle_id": circle_id,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=2)).isoformat(),
        "venue_timezone": "Asia/Kolkata",
        "place_label": "Community court",
    }


def direct(client, token, name, payload, action_id=None):
    return service.command(
        client.app.state.engine,
        token,
        Envelope(
            id=uuid4(),
            type="command",
            name=name,
            action_id=action_id or uuid4(),
            payload=payload,
        ),
    )


def test_invites_sessions_rotation_logout(client):
    invalid_token = "secret-too-short"
    invalid = client.post("/v1/auth/exchange", json={"invite_token": invalid_token})
    assert invalid.status_code == 422
    assert invalid_token not in invalid.text
    token = auth.create_invite(client.app.state.engine)
    response = client.post(
        "/v1/auth/exchange", json={"invite_token": token, "display_name": "Sara"}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    pair = response.json()
    assert client.post("/v1/auth/exchange", json={"invite_token": token}).status_code == 401
    with transaction(client.app.state.engine) as db:
        record = db.exec(select(AuthSession)).one()
        assert pair["access_token"] != record.access_hash
        assert record.access_hash == auth.digest(pair["access_token"])
    rotated = client.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert rotated.status_code == 200
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code
        == 401
    )
    with pytest.raises(AppError, match="refresh"):
        service.changes(client.app.state.engine, pair["access_token"], 0)
    fresh = rotated.json()["access_token"]
    assert (
        client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {fresh}"}).status_code
        == 204
    )
    with pytest.raises(AppError):
        service.changes(client.app.state.engine, fresh, 0)


def test_circle_plan_chat_and_resume(client):
    alice, bob, outsider = [login(client, name) for name in ["Alice", "Bob", "Outsider"]]
    a_context, a_auth = connect(client, alice["access_token"])
    b_context, b_auth = connect(client, bob["access_token"])
    with a_context as a, b_context as b:
        a.send_json(a_auth)
        b.send_json(b_auth)
        assert a.receive_json()["type"] == b.receive_json()["type"] == "ready"
        circle = result(a, "circle.create", {"name": "Sunday crew"})
        result(a, "circle.invite", {"circle_id": circle["id"], "user_id": bob["user_id"]})
        assert result(b, "invitation.list", query=True)["items"][0]["circle_id"] == circle["id"]
        result(b, "circle.join", {"circle_id": circle["id"]})
        plan = result(a, "plan.create", plan_payload(circle["id"]))
        assert len(plan["participants"]) == 2
        rsvp = {"plan_id": plan["id"], "rsvp": "in", "version": 1}
        changed = result(b, "plan.rsvp", rsvp)
        assert (
            next(p for p in changed["participants"] if p["user_id"] == bob["user_id"])["version"]
            == 2
        )
        assert rpc(b, "plan.rsvp", rsvp)["error"]["code"] == "version_conflict"
        before = service.changes(client.app.state.engine, alice["access_token"], 0)["cursor"]
        action = str(uuid4())
        message = result(
            b, "message.send", {"plan_id": plan["id"], "body": "See you there!"}, action_id=action
        )
        assert (
            result(
                b,
                "message.send",
                {"plan_id": plan["id"], "body": "See you there!"},
                action_id=action,
            )
            == message
        )
        assert (
            rpc(b, "message.send", {"plan_id": plan["id"], "body": "Changed"}, action_id=action)[
                "error"
            ]["code"]
            == "action_conflict"
        )
        assert result(a, "message.history", {"plan_id": plan["id"]}, query=True)["items"] == [
            message
        ]
    context, hello = connect(client, alice["access_token"], before)
    with context as ws:
        ws.send_json(hello)
        assert ws.receive_json()["type"] == "ready"
        batch = ws.receive_json()
        assert [event["kind"] for event in batch["events"]] == ["message.created"]
        assert batch["events"][0]["data"] == message
    context, hello = connect(client, outsider["access_token"])
    with context as ws:
        ws.send_json(hello)
        ws.receive_json()
        assert (
            rpc(ws, "plan.get", {"plan_id": plan["id"]}, query=True)["error"]["code"] == "not_found"
        )
        assert (
            rpc(ws, "message.send", {"plan_id": plan["id"], "body": "No access"})["error"]["code"]
            == "not_found"
        )
        assert rpc(ws, "circle.join", {"circle_id": circle["id"]})["error"]["code"] == "not_found"
    # A fresh engine can recover both the session and feed from disk.
    engine = make_engine(str(client.app.state.engine.url))
    try:
        assert (
            service.changes(engine, alice["access_token"], before)["events"][0]["data"] == message
        )
    finally:
        engine.dispose()


def test_concurrent_retries_and_conflicts_are_atomic(client):
    user = login(client, "Sara")
    token = user["access_token"]
    plan = direct(client, token, "plan.create", plan_payload())
    action_id = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                direct,
                client,
                token,
                "message.send",
                {
                    "plan_id": plan["id"],
                    "body": "Only once",
                },
                action_id,
            )
            for _ in range(2)
        ]
        assert futures[0].result() == futures[1].result()
        futures = [
            pool.submit(
                direct,
                client,
                token,
                "plan.rsvp",
                {
                    "plan_id": plan["id"],
                    "rsvp": rsvp,
                    "version": 1,
                },
            )
            for rsvp in ("in", "out")
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except AppError as exc:
                outcomes.append(exc.code)
    assert outcomes.count("version_conflict") == 1
    with transaction(client.app.state.engine) as db:
        assert len(db.exec(select(Message)).all()) == 1
        assert len(db.exec(select(Receipt)).all()) == 3
        seqs = db.exec(select(Change.seq).order_by(Change.seq)).all()
        assert seqs == list(range(1, len(seqs) + 1))


def test_expiry_worker_and_revoked_delivery(client):
    user = login(client, "Sara")
    token = user["access_token"]
    plan = direct(client, token, "plan.create", plan_payload())
    engine = client.app.state.engine
    with transaction(engine, write=True) as db:
        saved = db.get(Plan, UUID(plan["id"]))
        saved.ends_at = now() - 2 * 86400
        job = db.exec(select(Job)).one()
        job.run_at = now() - 1
    with pytest.raises(AppError, match="read-only"):
        direct(client, token, "message.send", {"plan_id": plan["id"], "body": "Late"})
    assert run_once(engine) is True
    assert run_once(engine) is False
    with transaction(engine, write=True) as db:
        assert db.get(Plan, UUID(plan["id"])).archived
        count = len(db.exec(select(Change)).all())
        job = db.exec(select(Job)).one()
        job.state = "pending"  # Simulate replay of an already-applied job.
    assert run_once(engine) is True
    with transaction(engine, write=True) as db:
        assert len(db.exec(select(Change)).all()) == count
        db.delete(db.get(Participant, (UUID(plan["id"]), UUID(user["user_id"]))))
    batch = service.changes(engine, token, 0)
    assert batch["events"] == []  # Old changes cannot re-expose revoked plan data.
    assert batch["cursor"] > 0


def test_worker_recovers_expired_lease_and_bounds_retries(client):
    user = login(client, "Sara")
    plan = direct(client, user["access_token"], "plan.create", plan_payload())
    engine = client.app.state.engine
    with transaction(engine, write=True) as db:
        db.get(Plan, UUID(plan["id"])).ends_at = now() - 2 * 86400
        job = db.exec(select(Job)).one()
        job.state = "running"
        job.lease_until = now() - 1
        job.lease_token = uuid4()
        job.run_at = now() - 1
    assert run_once(engine)
    with transaction(engine, write=True) as db:
        job = db.exec(select(Job)).one()
        assert job.state == "done"
        assert db.get(Plan, UUID(plan["id"])).archived
        job.kind = "unknown"
        job.state = "pending"
        job.attempts = 4
        job.run_at = now() - 1
    assert run_once(engine)
    with transaction(engine) as db:
        job = db.exec(select(Job)).one()
        assert job.state == "failed"
        assert job.attempts == 5
    assert not run_once(engine)


def test_socket_validation_origin_and_logout(client):
    user = login(client, "Sara")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/v1/ws", headers={"origin": "https://untrusted.example"}):
            pass
    context, hello = connect(client, user["access_token"])
    with context as ws:
        ws.send_json(hello)
        assert ws.receive_json()["type"] == "ready"
        ws.send_text("not json")
        assert ws.receive_json()["error"]["code"] == "invalid_payload"
        assert (
            rpc(ws, "places.search", {"query": "coffee"}, query=True)["error"]["code"]
            == "integration_disabled"
        )
        auth.logout(client.app.state.engine, user["access_token"])
        assert ws.receive_json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "change",
    [
        {"venue_timezone": "No/Such_Zone"},
        {"latitude": 12.9},
        {"starts_at": "2030-01-01T12:00:00"},
        {"title": " "},
    ],
)
def test_invalid_plan_inputs_do_not_write(client, change):
    user = login(client, "Sara")
    with pytest.raises(AppError):
        direct(client, user["access_token"], "plan.create", plan_payload() | change)
    with transaction(client.app.state.engine) as db:
        assert db.exec(select(Plan)).all() == []
