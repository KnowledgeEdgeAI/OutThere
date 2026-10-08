from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, select

from outthere import v2
from outthere.db import transaction
from outthere.delivery import DeliveryEvent, MessageAcceptance
from outthere.errors import AppError
from outthere.main import create_app
from outthere.models import now
from outthere.product_models import Snapshot
from outthere.settings import Settings
from outthere.v2_contracts import Frame
from outthere.worker import run_once


@pytest.fixture
def backend(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'product.db'}",
        auth_mode="unverified_phone",
        auth_retry_key=Fernet.generate_key().decode(),
        sync_poll_seconds=0.05,
        _env_file=None,
    )
    app = create_app(settings)
    SQLModel.metadata.create_all(app.state.engine)
    with TestClient(app):

        def login(phone, name, platform="web"):
            return v2.handle(
                app.state.engine,
                settings,
                request(
                    "auth.login",
                    {
                        "phone": phone,
                        "name": name,
                        "installation_id": str(uuid4()),
                        "platform": platform,
                    },
                ),
                None,
                None,
            )

        yield app.state.engine, settings, login


def request(name, payload=None):
    return Frame(
        v=2,
        id=uuid4(),
        type=v2.CONTRACTS[name][0],
        name=name,
        action_id=uuid4(),
        issued_at=datetime.now(UTC),
        payload=payload or {},
    )


def call(backend, pair, name, payload=None, intent=None):
    engine, settings, _ = backend
    return v2.handle(
        engine,
        settings,
        intent or request(name, payload),
        pair["access_token"],
        UUID(pair["device_id"]),
    )


def plan_fields(**kwargs):
    return {
        "plan_id": str(uuid4()),
        "title": "Walk",
        "starts_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "ends_at": (datetime.now(UTC) + timedelta(days=1, hours=2)).isoformat(),
        **kwargs,
    }


def test_invitation_snapshot_replay_and_removal(backend):
    _, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    circle_id = str(uuid4())
    create = request("circle.create", {"circle_id": circle_id, "name": "Friends"})
    assert call(backend, host, "circle.create", intent=create) == call(
        backend, host, "circle.create", intent=create
    )
    call(backend, host, "circle.invite", {"circle_id": circle_id, "user_id": guest["user_id"]})
    call(backend, guest, "circle.invitation.accept", {"circle_id": circle_id})
    plan = call(backend, host, "plan.create", plan_fields(circle_ids=[circle_id]))
    assert "participants" not in call(backend, guest, "plan.get", {"plan_id": plan["id"]})
    assert (
        call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})["approval_state"]
        == "requested"
    )
    with pytest.raises(AppError):
        call(backend, guest, "room.get", {"room_id": plan["id"]})
    call(backend, host, "plan.join.approve", {"plan_id": plan["id"], "user_id": guest["user_id"]})
    snapshot = call(backend, guest, "sync.start")
    call(backend, guest, "plan.rsvp", {"plan_id": plan["id"], "rsvp": "in", "expected_version": 1})
    replay = call(
        backend, guest, "sync.resume", {"cursor": snapshot["cursor"], "epoch": snapshot["epoch"]}
    )
    assert replay["changes"][-1]["data"]["participants"]
    call(backend, guest, "sync.ack", {"cursor": replay["cursor"], "epoch": replay["epoch"]})
    call(backend, host, "plan.member.remove", {"plan_id": plan["id"], "user_id": guest["user_id"]})
    with pytest.raises(AppError, match="Restart"):
        call(backend, guest, "sync.resume", {"cursor": replay["cursor"], "epoch": replay["epoch"]})
    with pytest.raises(AppError, match="Restart"):
        call(backend, guest, "sync.page", {"snapshot_id": snapshot["snapshot_id"]})
    fresh = call(backend, guest, "sync.start")
    summary = next(i["data"] for i in fresh["items"] if i["entity"] == "plan")
    assert "participants" not in summary
    with pytest.raises(AppError):
        call(backend, guest, "room.get", {"room_id": plan["id"]})


def test_snapshot_stability_routes_and_conflicts(backend):
    _, _, login = backend
    host = login("+919876543210", "Host")
    fields = plan_fields(
        stops=[
            {
                "stop_id": str(uuid4()),
                "order": 0,
                "label": "Park",
                "latitude": 12.9,
                "longitude": 77.6,
            }
        ]
    )
    plan = call(backend, host, "plan.create", fields)
    snapshot = call(backend, host, "sync.start", {"limit": 1})
    edit = fields | {"title": "New walk", "expected_version": plan["version"]}
    assert call(backend, host, "plan.update", edit)["version"] == 2
    old = call(backend, host, "sync.page", {"snapshot_id": snapshot["snapshot_id"], "after": 1})
    assert old["items"][0]["data"]["title"] == "Walk"
    replay = call(
        backend, host, "sync.resume", {"cursor": snapshot["cursor"], "epoch": snapshot["epoch"]}
    )
    assert replay["changes"][0]["data"]["title"] == "New walk"
    with pytest.raises(AppError, match="Refresh"):
        call(backend, host, "plan.update", edit)
    with transaction(backend[0], write=True) as db:
        db.get(Snapshot, UUID(snapshot["snapshot_id"])).expires_at = now() - 1
    with pytest.raises(AppError, match="Restart"):
        call(backend, host, "sync.page", {"snapshot_id": snapshot["snapshot_id"]})


def test_two_device_ack_retry_and_body_cleanup(backend):
    engine, _, login = backend
    host, host_second = login("+919876543210", "Host"), login("+919876543210", "Host")
    guest, guest_second = login("+919876543211", "Guest"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    intent = request(
        "message.send",
        {
            "room_id": plan["id"],
            "message_id": str(uuid4()),
            "content": {"kind": "text", "text": "Temporary secret"},
        },
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: call(backend, host, "message.send", intent=intent), [0, 1])
        )
    assert results[0] == results[1]
    event = results[0]["event_id"]
    assert call(backend, host, "delivery.pull")["items"] == []
    for pair in [host_second, guest, guest_second]:
        assert (
            call(backend, pair, "delivery.pull")["items"][0]["content"]["text"]
            == "Temporary secret"
        )
        call(backend, pair, "delivery.ack", {"event_ids": [event]})
        assert call(backend, pair, "delivery.pull")["items"] == []
    with transaction(engine) as db:
        assert db.exec(select(DeliveryEvent)).all() == []
        receipt = db.exec(select(MessageAcceptance)).one()
        assert "Temporary secret" not in str(receipt.model_dump())
        assert receipt.final_summary["delivered"] == 3
    assert call(backend, host, "message.send", intent=intent) == results[0]
    assert (
        call(backend, host, "delivery.status", {"message_ids": [intent.payload["message_id"]]})[
            "items"
        ][0]["state"]
        == "finished"
    )
    assert (
        call(backend, guest, "delivery.status", {"message_ids": [intent.payload["message_id"]]})[
            "items"
        ][0]["state"]
        == "unknown"
    )


def test_expiry_removal_and_unauthorized_ack(backend):
    engine, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    stranger = login("+919876543212", "Stranger")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    sent = call(
        backend,
        host,
        "message.send",
        {
            "room_id": plan["id"],
            "message_id": str(uuid4()),
            "content": {"kind": "text", "text": "Expire"},
        },
    )
    with pytest.raises(AppError):
        call(backend, stranger, "delivery.ack", {"event_ids": [sent["event_id"]]})
    with transaction(engine, write=True) as db:
        db.exec(select(DeliveryEvent)).one().expires_at = now() - 1
    assert not run_once(engine)
    assert call(backend, guest, "delivery.pull")["items"] == []
    with transaction(engine) as db:
        assert db.exec(select(MessageAcceptance)).one().final_summary["expired"] == 1
    call(
        backend,
        host,
        "message.send",
        {
            "room_id": plan["id"],
            "message_id": str(uuid4()),
            "content": {"kind": "text", "text": "Remove"},
        },
    )
    call(backend, host, "plan.member.remove", {"plan_id": plan["id"], "user_id": guest["user_id"]})
    assert call(backend, guest, "delivery.pull")["items"] == []
    with transaction(engine) as db:
        assert db.exec(select(DeliveryEvent)).all() == []


def test_money_rounding_allocation_races_and_reversal(backend):
    _, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    expense = call(
        backend,
        host,
        "expense.create",
        {
            "plan_id": plan["id"],
            "expense_id": str(uuid4()),
            "payer_id": host["user_id"],
            "amount_minor": 101,
            "currency": "INR",
            "description": "Tickets",
            "equal_user_ids": [host["user_id"], guest["user_id"]],
        },
    )
    assert sum(s["amount_minor"] for s in expense["shares"]) == 101
    share = next(s["amount_minor"] for s in expense["shares"] if s["user_id"] == guest["user_id"])
    positions = call(backend, host, "balance.list", {"plan_id": plan["id"]})["items"]
    assert sum(p["net_minor"] for p in positions) == 0
    proposals = [
        call(
            backend,
            guest,
            "settlement.propose",
            {
                "plan_id": plan["id"],
                "settlement_id": str(uuid4()),
                "to_user_id": host["user_id"],
                "currency": "INR",
                "allocations": [{"expense_id": expense["id"], "amount_minor": share}],
            },
        )
        for _ in range(2)
    ]

    def confirm(proposal):
        try:
            return call(
                backend,
                host,
                "settlement.confirm",
                {
                    "plan_id": plan["id"],
                    "settlement_id": proposal["settlement_id"],
                    "expected_version": 1,
                },
            )
        except AppError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, proposals))
    assert results.count("version_conflict") == 1
    confirmed = next(r for r in results if isinstance(r, dict))
    assert call(backend, host, "balance.list", {"plan_id": plan["id"]})["items"] == []
    with pytest.raises(AppError, match="Reverse"):
        call(
            backend,
            host,
            "expense.void",
            {"plan_id": plan["id"], "expense_id": expense["id"], "expected_version": 1},
        )
    call(
        backend,
        host,
        "settlement.reverse",
        {
            "plan_id": plan["id"],
            "settlement_id": confirmed["settlement_id"],
            "reversal_id": str(uuid4()),
            "expected_version": 2,
        },
    )
    assert call(backend, host, "balance.list", {"plan_id": plan["id"]})["items"] == positions
    call(backend, host, "plan.member.remove", {"plan_id": plan["id"], "user_id": guest["user_id"]})
    own = call(backend, guest, "expense.list", {"plan_id": plan["id"]})["items"]
    assert len(own[0]["shares"]) == 1
    assert own[0]["shares"][0]["user_id"] == guest["user_id"]


def test_album_file_integrity_permissions_and_revocation(backend):
    import hashlib

    from outthere.media import Media

    engine, settings, login = backend
    settings.media_directory = str(__import__("pathlib").Path(engine.url.database).parent / "media")
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    call(backend, guest, "plan.rsvp", {"plan_id": plan["id"], "rsvp": "in", "expected_version": 1})
    album = call(
        backend,
        host,
        "album.create",
        {"plan_id": plan["id"], "album_id": str(uuid4()), "title": "Walk"},
    )
    from io import BytesIO

    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (2, 2), "red").save(output, format="PNG")
    data = output.getvalue()
    media_id = str(uuid4())
    prepared = call(
        backend,
        host,
        "media.prepare",
        {
            "media_id": media_id,
            "plan_id": plan["id"],
            "purpose": "album",
            "mime": "image/png",
            "byte_size": len(data),
            "checksum": hashlib.sha256(data).hexdigest(),
        },
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.put(prepared["upload_url"], content=b"X" * len(data)).status_code == 422
        assert client.put(prepared["upload_url"], content=data).status_code == 200
        call(backend, host, "media.complete", {"media_id": media_id})
        call(
            backend,
            host,
            "album.media.add",
            {"album_id": album["id"], "media_id": media_id, "expected_version": 1},
        )
        signed = call(backend, guest, "media.read", {"media_id": media_id})
        assert client.get(signed["download_url"]).content == data
        call(
            backend,
            guest,
            "plan.rsvp",
            {"plan_id": plan["id"], "rsvp": "out", "expected_version": 2},
        )
        assert call(backend, guest, "album.get", {"album_id": album["id"]})["media"]
        assert (
            call(backend, guest, "wrap.get", {"plan_id": plan["id"]})["albums"][0]["id"]
            == album["id"]
        )
        call(backend, guest, "block.create", {"user_id": host["user_id"]})
        assert call(backend, guest, "album.list", {"plan_id": plan["id"]})["items"] == []
        with pytest.raises(AppError):
            call(backend, guest, "album.get", {"album_id": album["id"]})
        call(backend, guest, "block.delete", {"user_id": host["user_id"]})
        call(
            backend,
            host,
            "plan.member.remove",
            {"plan_id": plan["id"], "user_id": guest["user_id"]},
        )
        assert client.get(signed["download_url"]).status_code == 404
        with pytest.raises(AppError):
            call(backend, guest, "album.get", {"album_id": album["id"]})
    with transaction(engine) as db:
        assert db.get(Media, UUID(media_id)).expires_at is None


def test_poll_claims_and_meeting_version(backend):
    from outthere.coordination import Artifact

    engine, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    options = [{"option_id": str(uuid4()), "label": label} for label in ["Cafe", "Park"]]
    poll = call(
        backend,
        host,
        "artifact.create",
        {
            "plan_id": plan["id"],
            "artifact_id": str(uuid4()),
            "data": {"kind": "poll", "question": "Where?", "options": options},
        },
    )
    call(
        backend,
        guest,
        "artifact.respond",
        {
            "plan_id": plan["id"],
            "artifact_id": poll["id"],
            "option_id": options[0]["option_id"],
            "expected_version": 0,
        },
    )
    projected = call(backend, host, "artifact.list", {"plan_id": plan["id"]})["items"][0]
    assert projected["own_response"] is None
    assert projected["data"]["counts"][options[0]["option_id"]] == 1
    with transaction(engine, write=True) as db:
        db.get(Artifact, UUID(poll["id"])).closes_at = now() - 1
    run_once(engine)
    closed = call(backend, host, "artifact.list", {"plan_id": plan["id"]})["items"][0]
    assert closed["state"] == "closed"
    assert closed["data"]["result"] == "winner"
    with pytest.raises(AppError, match="closed"):
        call(
            backend,
            guest,
            "artifact.respond",
            {
                "plan_id": plan["id"],
                "artifact_id": poll["id"],
                "option_id": options[1]["option_id"],
                "expected_version": 1,
            },
        )
    item_id = str(uuid4())
    bring = call(
        backend,
        host,
        "artifact.create",
        {
            "plan_id": plan["id"],
            "artifact_id": str(uuid4()),
            "data": {"kind": "bring", "items": [{"item_id": item_id, "label": "Water"}]},
        },
    )
    claim = {
        "plan_id": plan["id"],
        "artifact_id": bring["id"],
        "item_id": item_id,
        "expected_version": 0,
    }
    call(backend, guest, "artifact.respond", claim)
    with pytest.raises(AppError):
        call(backend, host, "artifact.respond", claim | {"expected_version": 1})
    location = call(
        backend,
        host,
        "artifact.create",
        {
            "plan_id": plan["id"],
            "artifact_id": str(uuid4()),
            "data": {"kind": "location", "label": "Gate", "latitude": 12.9, "longitude": 77.6},
        },
    )
    call(
        backend,
        host,
        "plan.meeting.set",
        {
            "plan_id": plan["id"],
            "artifact_id": location["id"],
            "expected_version": 1,
            "expected_plan_version": 2,
        },
    )
    call(
        backend,
        guest,
        "artifact.respond",
        {
            "plan_id": plan["id"],
            "artifact_id": location["id"],
            "artifact_version": 2,
            "expected_version": 0,
        },
    )
    updated = call(
        backend,
        host,
        "artifact.update",
        {
            "plan_id": plan["id"],
            "artifact_id": location["id"],
            "expected_version": 2,
            "data": {
                "kind": "location",
                "label": "Other gate",
                "latitude": 13.0,
                "longitude": 77.6,
            },
        },
    )
    assert updated["version"] == 3
    with pytest.raises(AppError):
        call(
            backend,
            guest,
            "artifact.respond",
            {
                "plan_id": plan["id"],
                "artifact_id": location["id"],
                "artifact_version": 2,
                "expected_version": 1,
            },
        )
    call(backend, host, "plan.member.remove", {"plan_id": plan["id"], "user_id": guest["user_id"]})
    items = call(backend, host, "artifact.list", {"plan_id": plan["id"]})["items"]
    assert next(i for i in items if i["id"] == bring["id"])["claims"][0]["user_id"] is None


def test_ripple_private_responses_and_single_conversion(backend):
    _, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    another = login("+919876543212", "Another")
    slot_id = str(uuid4())
    fields = plan_fields()
    ripple = call(
        backend,
        host,
        "ripple.create",
        {
            "ripple_id": str(uuid4()),
            "idea": "Walk?",
            "user_ids": [guest["user_id"], another["user_id"], guest["user_id"]],
            "slots": [
                {
                    "slot_id": slot_id,
                    "starts_at": fields["starts_at"],
                    "ends_at": fields["ends_at"],
                    "venue_timezone": "Asia/Kolkata",
                }
            ],
        },
    )
    assert len(ripple["responses"]) == 2
    call(
        backend,
        guest,
        "ripple.respond",
        {
            "ripple_id": ripple["id"],
            "expected_version": 0,
            "choice": "up_for_it",
            "selected_slot_ids": [slot_id],
            "note": "Private reply",
        },
    )
    other_view = call(backend, another, "ripple.list")["items"][0]
    assert other_view["counts"]["up_for_it"] == 1
    assert "Private reply" not in str(other_view)
    convert = {
        "ripple_id": ripple["id"],
        "expected_version": 1,
        "plan": fields | {"invitee_ids": [guest["user_id"]]},
    }
    first = call(backend, host, "ripple.convert", convert)
    second = call(
        backend,
        host,
        "ripple.convert",
        convert | {"plan": fields | {"plan_id": str(uuid4()), "invitee_ids": [guest["user_id"]]}},
    )
    assert first == second
    plan = call(backend, host, "plan.get", {"plan_id": first["plan_id"]})
    assert len(plan["participants"]) == 1
    with pytest.raises(AppError, match="closed"):
        call(
            backend,
            guest,
            "ripple.respond",
            {"ripple_id": ripple["id"], "expected_version": 1, "choice": "cannot"},
        )


def test_matching_density_anonymity_mutual_hello_and_block(backend):
    _, settings, login = backend
    settings.match_jitter_seconds = 0
    pairs = [login(f"+91987654321{i}", f"Person {i}") for i in range(4)]
    opens = []
    for pair in pairs:
        opens.append(
            call(
                backend,
                pair,
                "open.create",
                {
                    "open_id": str(uuid4()),
                    "latitude": 12.9,
                    "longitude": 77.6,
                    "radius_m": 5000,
                    "starts_at": datetime.now(UTC).isoformat(),
                    "ends_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                },
            )
        )
        if len(opens) < 4:
            assert (
                call(backend, pairs[0], "overlap.list", {"open_id": opens[0]["id"]})["state"]
                == "insufficient_density"
            )
    cards = call(backend, pairs[0], "overlap.list", {"open_id": opens[0]["id"]})["items"]
    assert len(cards) == 3
    assert all(
        "phone" not in str(c) and "Person" not in str(c) and "latitude" not in str(c) for c in cards
    )
    chosen = cards[0]
    # Determine the matching recipient without exposing identity on the anonymous card.
    from outthere.matching import Overlap
    from outthere.matching import pair as overlap_pair

    with transaction(backend[0]) as db:
        row = db.get(Overlap, UUID(chosen["id"]))
        a, b = overlap_pair(db, row)
        other_id = str(b.user_id if str(a.user_id) == pairs[0]["user_id"] else a.user_id)
    other = next(p for p in pairs if p["user_id"] == other_id)
    first = call(
        backend,
        pairs[0],
        "overlap.respond",
        {"overlap_id": chosen["id"], "choice": "hi", "expected_version": 1},
    )
    hello = call(
        backend,
        other,
        "overlap.respond",
        {"overlap_id": chosen["id"], "choice": "hi", "expected_version": first["version"]},
    )
    assert hello["state"] == "hello"
    assert call(backend, pairs[0], "room.get", {"room_id": hello["room_id"]})["plan_id"] is None
    sent = call(
        backend,
        pairs[0],
        "message.send",
        {
            "room_id": hello["room_id"],
            "message_id": str(uuid4()),
            "content": {"kind": "text", "text": "Hi"},
        },
    )
    assert call(backend, other, "delivery.pull")["items"][0]["event_id"] == sent["event_id"]
    snapshot = call(backend, other, "sync.start")
    assert any(i["entity"] == "overlap" for i in snapshot["items"])
    call(backend, pairs[0], "block.create", {"user_id": other["user_id"]})
    assert call(backend, other, "delivery.pull")["items"] == []
    with pytest.raises(AppError):
        call(backend, other, "room.get", {"room_id": hello["room_id"]})
    with pytest.raises(AppError, match="Restart"):
        call(
            backend,
            other,
            "sync.resume",
            {"cursor": snapshot["cursor"], "epoch": snapshot["epoch"]},
        )
    assert not any(
        i["entity"] == "overlap" and i["entity_id"] == hello["room_id"]
        for i in call(backend, other, "sync.start")["items"]
    )


def test_attachment_ack_is_independent_of_message_ack(backend):
    import hashlib
    from io import BytesIO
    from pathlib import Path

    from PIL import Image

    from outthere.delivery import AttachmentTarget

    engine, settings, login = backend
    settings.media_directory = str(Path(engine.url.database).parent / "files")
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    output = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(output, format="PNG")
    data = output.getvalue()
    media_id = str(uuid4())
    prepared = call(
        backend,
        host,
        "media.prepare",
        {
            "plan_id": plan["id"],
            "media_id": media_id,
            "purpose": "chat",
            "mime": "image/png",
            "byte_size": len(data),
            "checksum": hashlib.sha256(data).hexdigest(),
        },
    )
    with TestClient(create_app(settings)) as client:
        assert client.put(prepared["upload_url"], content=data).status_code == 200
        call(backend, host, "media.complete", {"media_id": media_id})
        sent = call(
            backend,
            host,
            "message.send",
            {
                "room_id": plan["id"],
                "message_id": str(uuid4()),
                "content": {
                    "kind": "image",
                    "media_ids": [media_id],
                    "caption": "Temporary caption",
                },
            },
        )
        call(backend, guest, "delivery.ack", {"event_ids": [sent["event_id"]]})
        assert call(backend, guest, "delivery.pull")["items"] == []
        with transaction(engine) as db:
            assert db.get(DeliveryEvent, UUID(sent["event_id"])).payload == {}
            assert db.exec(select(AttachmentTarget)).one().downloaded_at is None
        signed = call(backend, guest, "media.read", {"media_id": media_id})
        assert client.get(signed["download_url"]).content == data
        call(
            backend,
            guest,
            "delivery.media.ack",
            {"event_id": sent["event_id"], "media_id": media_id},
        )
        with transaction(engine) as db:
            assert db.exec(select(DeliveryEvent)).all() == []
            assert db.exec(select(AttachmentTarget)).all() == []
        assert client.get(signed["download_url"]).status_code == 404


def test_personal_points_never_enter_snapshot_and_expire(backend):
    from outthere.coordination import PersonalPoint

    _, _, login = backend
    host = login("+919876543210", "Host")
    plan = call(backend, host, "plan.create", plan_fields())
    point = call(
        backend,
        host,
        "artifact.create",
        {
            "plan_id": plan["id"],
            "artifact_id": str(uuid4()),
            "data": {
                "kind": "personal_location",
                "latitude": 1.25,
                "longitude": 2.5,
                "label": "Here",
                "captured_at": datetime.now(UTC).isoformat(),
            },
        },
    )
    snapshot = call(backend, host, "sync.start")
    assert "1.25" not in str(snapshot) and "2.5" not in str(snapshot)
    exact = call(
        backend,
        host,
        "artifact.point.get",
        {"plan_id": plan["id"], "artifact_id": point["id"], "expected_version": 1},
    )
    assert exact["latitude"] == 1.25
    with transaction(backend[0], write=True) as db:
        db.get(PersonalPoint, UUID(point["id"])).expires_at = now() - 1
    run_once(backend[0])
    with pytest.raises(AppError):
        call(
            backend,
            host,
            "artifact.point.get",
            {"plan_id": plan["id"], "artifact_id": point["id"], "expected_version": 1},
        )
    with transaction(backend[0]) as db:
        assert db.exec(select(PersonalPoint)).all() == []


def test_push_grace_ack_suppression_and_safe_jobs(backend, monkeypatch):
    from outthere import push
    from outthere.models import Job

    engine, settings, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest", "android")
    call(
        backend,
        guest,
        "device.push.register",
        {
            "token": "test-device-token-1234",
            "provider": "fcm",
            "platform": "android",
            "enabled_categories": ["messages"],
        },
    )
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    sent = call(
        backend,
        host,
        "message.send",
        {
            "room_id": plan["id"],
            "message_id": str(uuid4()),
            "content": {"kind": "text", "text": "Must not enter push"},
        },
    )
    with transaction(engine, write=True) as db:
        job = db.exec(select(Job).where(Job.kind == "push.notify")).one()
        assert "Must not enter push" not in str(job.model_dump())
        job.run_at = now() - 1
    notifications = []
    monkeypatch.setattr(push, "notify", lambda *args: notifications.append(args) or True)
    call(backend, guest, "delivery.ack", {"event_ids": [sent["event_id"]]})
    assert run_once(engine, settings)
    assert notifications == []
    call(
        backend,
        host,
        "message.send",
        {
            "room_id": plan["id"],
            "message_id": str(uuid4()),
            "content": {"kind": "text", "text": "Still not in push"},
        },
    )
    with transaction(engine, write=True) as db:
        db.exec(
            select(Job).where(Job.kind == "push.notify", Job.state == "pending")
        ).one().run_at = now() - 1
    assert run_once(engine, settings)
    assert len(notifications) == 1
    assert notifications[0][2] == "messages"


def test_places_session_tokens_and_provider_failures(backend):
    import httpx
    from pydantic import SecretStr

    from outthere.places_v2 import Details, Search, handle

    settings = backend[1]
    settings.maps_provider, settings.google_maps_api_key = "google", SecretStr("test-key")
    session = uuid4()
    requests = []

    def provider(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "suggestions": [
                        {"placePrediction": {"placeId": "p1", "text": {"text": "Park"}}}
                    ]
                },
            )
        return httpx.Response(
            200, json={"id": "p1", "location": {"latitude": 12.9, "longitude": 77.6}}
        )

    transport = httpx.MockTransport(provider)
    assert (
        handle(settings, "places.search", Search(query="Park", session_token=session), transport)[
            "items"
        ][0]["place_id"]
        == "p1"
    )
    assert (
        handle(
            settings, "places.details", Details(place_id="p1", session_token=session), transport
        )["latitude"]
        == 12.9
    )
    assert str(session) in requests[0].content.decode()
    assert requests[1].url.params["sessionToken"] == str(session)
    with pytest.raises(AppError, match="temporarily"):
        handle(
            settings,
            "places.search",
            Search(query="Park", session_token=session),
            httpx.MockTransport(lambda _: httpx.Response(503)),
        )


def test_account_deletion_revokes_identity_but_keeps_shared_money(backend):
    from outthere.models import User

    _, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    call(
        backend,
        host,
        "expense.create",
        {
            "plan_id": plan["id"],
            "expense_id": str(uuid4()),
            "payer_id": host["user_id"],
            "amount_minor": 100,
            "currency": "INR",
            "description": "Fare",
            "equal_user_ids": [host["user_id"], guest["user_id"]],
        },
    )
    assert call(backend, guest, "account.delete", {"expected_version": 1})["deleted"]
    with pytest.raises(AppError):
        call(backend, guest, "profile.get")
    with transaction(backend[0]) as db:
        row = db.get(User, UUID(guest["user_id"]))
        assert row.phone is None and row.display_name == "Deleted account"
    assert call(backend, host, "balance.list", {"plan_id": plan["id"]})["items"]


def test_live_socket_sync_chat_and_typing(backend):

    _, settings, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    fields = plan_fields()
    plan = call(backend, host, "plan.create", fields | {"invitee_ids": [guest["user_id"]]})
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    snapshot = call(backend, guest, "sync.start")

    def rpc(socket, name, payload=None):
        intent = request(name, payload)
        socket.send_json(intent.model_dump(mode="json"))
        while True:
            result = socket.receive_json()
            if result.get("id") == str(intent.id):
                assert result["type"] == "result", result
                return result["data"]

    def event(socket, name):
        while True:
            frame = socket.receive_json()
            if frame.get("name") == name:
                return frame["payload"]

    with TestClient(create_app(settings)) as client:
        with client.websocket_connect("/v2/ws") as a, client.websocket_connect("/v2/ws") as b:
            for socket, pair in [(a, host), (b, guest)]:
                rpc(
                    socket,
                    "auth.resume",
                    {"device_id": pair["device_id"], "access_token": pair["access_token"]},
                )
            rpc(b, "sync.resume", {"cursor": snapshot["cursor"], "epoch": snapshot["epoch"]})
            changed = rpc(
                a, "plan.update", fields | {"expected_version": 2, "title": "Updated walk"}
            )
            assert event(b, "sync.batch")["changes"][0]["data"]["title"] == changed["title"]
            sent = rpc(
                a,
                "message.send",
                {
                    "room_id": plan["id"],
                    "message_id": str(uuid4()),
                    "content": {"kind": "text", "text": "Live"},
                },
            )
            assert event(b, "delivery.batch")["items"][0]["event_id"] == sent["event_id"]
            rpc(b, "delivery.ack", {"event_ids": [sent["event_id"]]})
            rpc(a, "typing.update", {"room_id": plan["id"], "active": True})
            assert event(b, "typing.changed")["active"] is True


def test_all_contracts_forbid_unknown_fields_without_echoing_values():
    from outthere.service import validate

    for _, model in v2.CONTRACTS.values():
        with pytest.raises(AppError) as error:
            validate(model, {"__unknown_field__": "private-payload-value"})
        assert "private-payload-value" not in str(error.value)


def test_stale_cursor_resets_after_worker_retention(backend):
    from outthere.models import Change

    _, _, login = backend
    host = login("+919876543210", "Host")
    snapshot = call(backend, host, "sync.start")
    call(backend, host, "circle.create", {"circle_id": str(uuid4()), "name": "Friends"})
    with transaction(backend[0], write=True) as db:
        db.exec(select(Change)).one().created_at = now() - 31 * 86400
    assert not run_once(backend[0])
    with pytest.raises(AppError, match="Restart"):
        call(
            backend, host, "sync.resume", {"cursor": snapshot["cursor"], "epoch": snapshot["epoch"]}
        )


def test_push_adapters_sign_and_send_generic_payloads(backend):
    import json

    import httpx
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from pydantic import SecretStr

    from outthere import push
    from outthere.models import Device

    settings = backend[1]
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    settings.fcm_service_account = SecretStr(
        json.dumps(
            {
                "project_id": "outthere-test",
                "client_email": "test@example.invalid",
                "private_key": pem,
            }
        )
    )
    requests = []

    def provider(request):
        requests.append(request)
        if request.url.host == "oauth2.googleapis.com":
            assert b"assertion=" in request.content
            return httpx.Response(
                200, json={"access_token": "test-provider-token", "expires_in": 3600}
            )
        return httpx.Response(200, json={"name": "accepted"})

    transport = httpx.MockTransport(provider)
    device = Device(
        user_id=uuid4(),
        installation_id=uuid4(),
        platform="android",
        push_token="registration-token",
        push_provider="fcm",
        push_categories=["messages"],
    )
    assert push.notify(settings, device, "messages", uuid4(), transport)
    sent = json.loads(requests[-1].content)["message"]
    assert sent["notification"]["body"] == "You have an update"
    assert sent["token"] == "registration-token"
    key = ec.generate_private_key(ec.SECP256R1())
    settings.apns_private_key = SecretStr(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
    )
    settings.apns_key_id, settings.apns_team_id, settings.apns_topic = (
        "key-id",
        "team-id",
        "test.outthere",
    )
    device.platform, device.push_provider, device.push_token = "ios", "apns", "a" * 64
    assert push.notify(settings, device, "messages", uuid4(), transport)
    assert requests[-1].headers["apns-push-type"] == "alert"
    assert requests[-1].headers["apns-topic"] == "test.outthere"
    assert json.loads(requests[-1].content)["aps"]["alert"]["body"] == "You have an update"
    assert not push.notify(
        settings,
        device,
        "messages",
        uuid4(),
        httpx.MockTransport(lambda _: httpx.Response(410, json={"reason": "Unregistered"})),
    )


def test_reactions_deduplicate_distinct_intents_after_event_cleanup(backend):
    _, _, login = backend
    host, guest = login("+919876543210", "Host"), login("+919876543211", "Guest")
    plan = call(backend, host, "plan.create", plan_fields(invitee_ids=[guest["user_id"]]))
    call(backend, guest, "plan.join.request", {"plan_id": plan["id"]})
    message_id = str(uuid4())
    call(
        backend,
        host,
        "message.send",
        {
            "room_id": plan["id"],
            "message_id": message_id,
            "content": {"kind": "text", "text": "React"},
        },
    )
    reaction = {"room_id": plan["id"], "message_id": message_id, "emoji": "👍"}
    first = call(backend, guest, "message.reaction.add", reaction)
    call(backend, host, "delivery.ack", {"event_ids": [first["event_id"]]})
    assert not call(backend, guest, "message.reaction.add", reaction)["changed"]
    assert call(backend, guest, "message.reaction.remove", reaction)["changed"]
    assert not call(backend, guest, "message.reaction.remove", reaction)["changed"]
