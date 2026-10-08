"""Versioned account transport. Advertise only implemented capabilities."""

import asyncio
import hashlib
import json
import time
from collections import deque
from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import select

from outthere import (
    coordination,
    delivery,
    matching,
    media,
    money,
    places_v2,
    product,
    push,
    ripples,
    safety,
    sessions,
    sharing,
)
from outthere.db import transaction
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import ActionReceipt, AuthOperation, Device, User, now
from outthere.product_contracts import CONTRACTS as PRODUCT_CONTRACTS
from outthere.service import validate
from outthere.v2_contracts import (
    DeviceRevoke,
    Dispatch,
    Empty,
    Frame,
    Login,
    ProfileGet,
    ProfileUpdate,
    Renewal,
    Resume,
)

# Name, frame kind, payload model. This is also the source for client capability discovery.
CONTRACTS = {
    "auth.login": ("command", Login),
    "auth.resume": ("query", Resume),
    "auth.refresh": ("command", Renewal),
    "auth.logout": ("command", Empty),
    "profile.get": ("query", ProfileGet),
    "profile.update": ("command", ProfileUpdate),
    "device.list": ("query", Empty),
    "device.revoke": ("command", DeviceRevoke),
    "ping": ("query", Empty),
}
CONTRACTS.update(PRODUCT_CONTRACTS)
CONTRACTS.update(delivery.CONTRACTS)
CONTRACTS.update(money.CONTRACTS)
CONTRACTS.update(media.CONTRACTS)
CONTRACTS.update(coordination.CONTRACTS)
CONTRACTS.update(ripples.CONTRACTS)
CONTRACTS.update(safety.CONTRACTS)
CONTRACTS.update(matching.CONTRACTS)
CONTRACTS.update(places_v2.CONTRACTS)
CONTRACTS.update(sharing.CONTRACTS)
CONTRACTS.update(push.CONTRACTS)
AUTH = {"auth.login", "auth.resume", "auth.refresh"}


def contract_schemas() -> dict:
    return {
        name: {"type": kind, "payload": model.model_json_schema()}
        for name, (kind, model) in CONTRACTS.items()
    }


def current_profile(engine, token, device_id):
    with transaction(engine) as db:
        record = sessions.authenticate(db, token, device_id)
        return sessions.profile(db.get(User, record.user_id))


def handle(engine, settings, request: Frame, token: str | None, device_id: UUID | None):
    for attempt in range(3):
        try:
            return _handle(engine, settings, request, token, device_id)
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) in {"40P01", "40001"} and attempt < 2:
                continue
            if isinstance(exc, IntegrityError):
                raise
            raise AppError(
                "provider_unavailable", "Database temporarily unavailable", 503
            ) from None
    raise AssertionError("unreachable")


def _handle(engine, settings, request: Frame, token: str | None, device_id: UUID | None):
    entry = CONTRACTS.get(request.name)
    if entry is None:
        raise AppError("unsupported_version", "This capability is not implemented", 400)
    kind, model = entry
    if request.type != kind:
        raise AppError("invalid_input", "Wrong frame type for this event")
    try:
        data = validate(model, request.payload)
    except AppError as exc:
        raise AppError("invalid_input", exc.message, 422) from exc
    if request.name in places_v2.CONTRACTS:
        if not token or not device_id:
            raise AppError("unauthenticated", "Authenticate first", 401)
        with transaction(engine) as db:
            sessions.authenticate(db, token, device_id)
        return places_v2.handle(settings, request.name, data)
    with transaction(engine, write=True) as db:
        if db.bind.dialect.name == "postgresql":
            # Serialize shared audience mutations and consistent snapshots initially.
            db.execute(text("SELECT pg_advisory_xact_lock(73482109)"))
        # Bounded ephemeral operational state; no tokens survive their retry window.
        db.exec(delete(AuthOperation).where(AuthOperation.expires_at <= now()))
        db.exec(delete(ActionReceipt).where(ActionReceipt.expires_at <= now()))
        if request.name == "auth.login":
            if token:
                raise AppError("invalid_input", "Sign out before switching accounts")
            return sessions.login(db, settings, data)
        if request.name == "auth.resume":
            if token and device_id != data.device_id:
                raise AppError("invalid_input", "Reconnect to switch devices")
            record = sessions.authenticate(db, data.access_token, data.device_id)
            db.get(Device, data.device_id).last_seen_at = now()
            return {
                "user_id": str(record.user_id),
                "device_id": str(data.device_id),
                "profile": sessions.profile(db.get(User, record.user_id)),
                "capabilities": list(CONTRACTS),
            }
        if request.name == "auth.refresh":
            if token and device_id != data.device_id:
                raise AppError("invalid_input", "Reconnect to switch devices")
            return sessions.renew(db, settings, data)
        if not token or not device_id:
            raise AppError("unauthenticated", "Authenticate first", 401)
        # One account lock precedes device locks, including cross-device revocation.
        # Two devices revoking each other must not acquire those locks in reverse order.
        initial = sessions.authenticate(db, token, device_id)
        db.exec(select(User).where(User.id == initial.user_id).with_for_update()).one()
        device = db.exec(select(Device).where(Device.id == device_id).with_for_update()).first()
        record = sessions.authenticate(db, token, device_id)
        device.last_seen_at = now()
        user = db.get(User, record.user_id)
        if request.name == "ping":
            return {"server_time": now()}
        if request.name == "profile.get":
            if data.user_id is None or data.user_id == user.id:
                return sessions.profile(user)
            return sessions.related_profile(db, user.id, data.user_id)
        if request.name == "device.list":
            rows = db.exec(
                select(Device)
                .where(Device.user_id == user.id)
                .order_by(Device.created_at, Device.id)
                .limit(100)
            ).all()
            return {
                "items": [
                    {
                        "id": str(d.id),
                        "platform": d.platform,
                        "last_seen_at": d.last_seen_at,
                        "revoked_at": d.revoked_at,
                        "current": d.id == device_id,
                    }
                    for d in rows
                ]
            }
        if request.name == "auth.logout":
            sessions.revoke(db, user.id, device_id)
            return {"signed_out": True}
        if request.name in sharing.CONTRACTS and kind == "query":
            return sharing.handle(db, user, request.name, data)
        if request.name in matching.CONTRACTS and kind == "query":
            return matching.handle(db, settings, user, request.name, data)
        if request.name in safety.CONTRACTS and kind == "query":
            return safety.handle(db, user, request.name, data)
        ripples.cleanup(db)
        if request.name in ripples.CONTRACTS and kind == "query":
            return ripples.handle(db, user, request.name, data)
        coordination.cleanup(db)
        if request.name in coordination.CONTRACTS and kind == "query":
            return coordination.handle(db, user, request.name, data)
        if request.name in media.CONTRACTS and kind == "query":
            return media.handle(db, settings, user, device, request.name, data)
        if request.name in money.CONTRACTS and kind == "query":
            return money.handle(db, user, request.name, data)
        if request.name in delivery.CONTRACTS and request.name not in {
            "message.send",
            "message.reaction.add",
            "message.reaction.remove",
        }:
            return delivery.handle(db, user, device, request.name, data)
        if request.name in PRODUCT_CONTRACTS and kind == "query":
            return product.query(db, user, device, request.name, data)
        if request.name == "sync.ack":
            return product.handle(db, user, device, request.name, data)
        try:
            intent = Dispatch(action_id=request.action_id, issued_at=request.issued_at)
        except ValidationError as exc:
            raise AppError("invalid_input", "Mutations need action_id and issued_at", 422) from exc
        issued = int(intent.issued_at.timestamp())
        # The timestamp is immutable intent data, part of the hash. Enforced server-side,
        # even after receipt cleanup, so a stale request cannot execute again.
        if issued < now() - settings.action_retry_seconds or issued > now() + 60:
            raise AppError("expired", "Action expired; refresh and review before resubmitting", 409)
        canonical = json.dumps(
            [
                request.name,
                intent.issued_at.astimezone(UTC).isoformat(),
                data.model_dump(mode="json"),
            ],
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        if request.name == "message.send":
            if db.get(ActionReceipt, (user.id, intent.action_id)):
                raise AppError("action_conflict", "Action ID belongs to another request", 409)
            return delivery.send(db, user, device, data, intent.action_id, fingerprint)
        if db.get(delivery.MessageAcceptance, (user.id, intent.action_id)):
            raise AppError("action_conflict", "Action ID belongs to a message", 409)
        receipt = db.get(ActionReceipt, (user.id, intent.action_id))
        if receipt is not None:
            if receipt.request_hash != fingerprint:
                raise AppError("action_conflict", "Action ID belongs to another request", 409)
            return receipt.result
        if (
            db.exec(
                select(money.Expense).where(money.Expense.operation_id == intent.action_id)
            ).first()
            or db.exec(
                select(money.Settlement).where(money.Settlement.operation_id == intent.action_id)
            ).first()
        ):
            raise AppError("action_conflict", "This permanent money operation already exists", 409)
        receipt = ActionReceipt(
            user_id=user.id,
            action_id=intent.action_id,
            request_hash=fingerprint,
            result={},
            expires_at=now() + 30 * 86400,
        )
        db.add(receipt)
        db.flush()
        if request.name == "profile.update":
            user = db.exec(select(User).where(User.id == user.id).with_for_update()).one()
            if user.version != data.expected_version:
                raise AppError("version_conflict", "Profile changed; refresh and review", 409)
            if "dp_media_id" in data.model_fields_set:
                if user.dp_media_id and user.dp_media_id != data.dp_media_id:
                    old = db.get(media.Media, user.dp_media_id)
                    if old:
                        old.expires_at = now() + 86400
                if data.dp_media_id is not None:
                    row = db.get(media.Media, data.dp_media_id)
                    if (
                        row is None
                        or row.uploader_id != user.id
                        or row.purpose != "profile"
                        or row.state != "ready"
                    ):
                        raise AppError("not_found", "Profile image not found", 404)
                    row.expires_at = None
                user.dp_media_id = data.dp_media_id
            user.display_name = data.name
            user.version += 1
            result = sessions.profile(user)
            emit(db, {user.id}, "v2.profile", user.id)
        elif request.name in delivery.CONTRACTS:
            result = delivery.handle(db, user, device, request.name, data)
        elif request.name in push.CONTRACTS:
            result = push.handle(db, device, request.name, data)
        elif request.name in sharing.CONTRACTS:
            result = sharing.handle(db, user, request.name, data)
        elif request.name in matching.CONTRACTS:
            result = matching.handle(db, settings, user, request.name, data)
        elif request.name in safety.CONTRACTS:
            result = safety.handle(db, user, request.name, data)
        elif request.name in ripples.CONTRACTS:
            result = ripples.handle(db, user, request.name, data)
        elif request.name in coordination.CONTRACTS:
            result = coordination.handle(db, user, request.name, data)
        elif request.name in media.CONTRACTS:
            result = media.handle(db, settings, user, device, request.name, data)
        elif request.name in money.CONTRACTS:
            result = money.handle(db, user, request.name, data, intent.action_id)
        elif request.name in PRODUCT_CONTRACTS:
            result = product.handle(db, user, device, request.name, data)
        else:
            sessions.revoke(db, user.id, data.device_id)
            result = {"device_id": str(data.device_id), "revoked": True}
        receipt.result = result
        return result


def router(engine, settings) -> APIRouter:
    routes = APIRouter()
    windows: dict[str, deque] = {}
    connections: dict[str, int] = {}
    peers: dict[WebSocket, tuple] = {}

    def limit(key: str, maximum: int):
        tick = time.monotonic()
        # Expire unused keys before insertion; reject overflow rather than unbounded growth.
        for candidate in list(windows):
            if not windows[candidate] or windows[candidate][-1] <= tick - 60:
                del windows[candidate]
        if key not in windows and len(windows) >= 1024:
            raise AppError("rate_limited", "Try again shortly", 429)
        window = windows.setdefault(key, deque())
        while window and window[0] <= tick - 60:
            window.popleft()
        if len(window) >= maximum:
            raise AppError("rate_limited", "Try again in a minute", 429)
        window.append(tick)

    async def send(socket, frame):
        await asyncio.wait_for(socket.send_json({"v": 2, **frame}), timeout=5)

    @routes.websocket("/v2/ws")
    async def websocket(socket: WebSocket):
        origin = socket.headers.get("origin")
        if origin is not None and origin not in settings.allowed_origins:
            await socket.close(code=1008)
            return
        await socket.accept()
        token = None
        device_id = None
        account = None
        profile_version = None
        sync_cursor = None
        sync_epoch = None
        deadline = time.monotonic() + 10
        receive_task = None
        try:
            while True:
                try:
                    timeout = (
                        settings.sync_poll_seconds
                        if token
                        else max(0.01, deadline - time.monotonic())
                    )
                    if receive_task is None:
                        receive_task = asyncio.create_task(socket.receive_text())
                    # A polling timeout must not cancel an ASGI receive after it consumed
                    # a frame. Keep one receive alive until the request is processed.
                    raw = await asyncio.wait_for(asyncio.shield(receive_task), timeout=timeout)
                    receive_task = None
                except TimeoutError:
                    if not token:
                        await socket.close(code=1008)
                        return
                    current = await run_in_threadpool(current_profile, engine, token, device_id)
                    if current["version"] != profile_version:
                        await send(
                            socket, {"type": "event", "name": "profile.changed", "payload": current}
                        )
                        profile_version = current["version"]
                    if sync_cursor is not None:
                        try:
                            batch = await run_in_threadpool(
                                handle,
                                engine,
                                settings,
                                Frame(
                                    v=2,
                                    id=UUID(int=1),
                                    type="query",
                                    name="sync.resume",
                                    payload={"cursor": sync_cursor, "epoch": sync_epoch},
                                ),
                                token,
                                device_id,
                            )
                            if batch["cursor"] != sync_cursor:
                                await send(
                                    socket,
                                    {"type": "event", "name": "sync.batch", "payload": batch},
                                )
                                sync_cursor = batch["cursor"]
                        except AppError as exc:
                            if exc.code != "cursor_reset_required":
                                raise
                            await send(
                                socket,
                                {
                                    "type": "event",
                                    "name": "sync.access_revoked",
                                    "payload": {"reset_required": True},
                                },
                            )
                            sync_cursor = None
                    batch = await run_in_threadpool(
                        handle,
                        engine,
                        settings,
                        Frame(
                            v=2,
                            id=UUID(int=1),
                            type="query",
                            name="delivery.pull",
                            payload={"limit": 10},
                        ),
                        token,
                        device_id,
                    )
                    if batch["items"]:
                        await send(
                            socket, {"type": "event", "name": "delivery.batch", "payload": batch}
                        )
                    continue
                request_id = None
                try:
                    if len(raw.encode()) > 64 * 1024:
                        raise AppError("invalid_input", "Frame exceeds 64 KiB", 413)
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        try:
                            request_id = str(UUID(str(parsed.get("id"))))
                        except ValueError:
                            pass
                    request = Frame.model_validate(parsed)
                    request_id = str(request.id)
                    limit(f"ip:{socket.client.host}", 120)
                    if not token and request.name not in AUTH:
                        raise AppError("unauthenticated", "Authenticate first", 401)
                    if request.name == "auth.login":
                        login_data = Login.model_validate(request.payload)
                        limit(f"phone:{sessions.digest(login_data.phone)}", 10)
                    result = await run_in_threadpool(
                        handle, engine, settings, request, token, device_id
                    )
                    if request.name in AUTH:
                        next_token = (
                            request.payload["access_token"]
                            if request.name == "auth.resume"
                            else result["access_token"]
                        )
                        next_device = UUID(result["device_id"])
                        with transaction(engine) as db:
                            record = sessions.authenticate(db, next_token, next_device)
                            next_account = str(record.user_id)
                        if account is None:
                            if connections.get(next_account, 0) >= 4:
                                raise AppError(
                                    "rate_limited", "Four active connections per account", 429
                                )
                            connections[next_account] = connections.get(next_account, 0) + 1
                            account = next_account
                        token, device_id = next_token, next_device
                        peers[socket] = (token, device_id, UUID(account))
                        result["capabilities"] = list(CONTRACTS)
                    if request.name == "typing.update":
                        for peer, (peer_token, peer_device, peer_user) in list(peers.items()):
                            if peer is socket:
                                continue

                            def can_receive(
                                peer_token=peer_token,
                                peer_device=peer_device,
                                peer_user=peer_user,
                                result=result,
                            ):
                                with transaction(engine) as db:
                                    sessions.authenticate(db, peer_token, peer_device)
                                    delivery.room_access(db, peer_user, UUID(result["room_id"]))
                                    return not safety.blocked(
                                        db, UUID(result["sender_id"]), peer_user
                                    )

                            try:
                                if await run_in_threadpool(can_receive):
                                    await send(
                                        peer,
                                        {
                                            "type": "event",
                                            "name": "typing.changed",
                                            "payload": result,
                                        },
                                    )
                            except (AppError, TimeoutError, RuntimeError):
                                continue
                    if request.name == "sync.resume":
                        sync_cursor, sync_epoch = result["cursor"], result["epoch"]
                    if request.name == "sync.start":
                        sync_cursor = None
                    if "profile" in result:
                        profile_version = result["profile"]["version"]
                    await send(socket, {"type": "result", "id": request_id, "data": result})
                    if request.name in {"auth.logout", "account.delete"} or (
                        request.name == "device.revoke" and result["device_id"] == str(device_id)
                    ):
                        await socket.close(code=1000)
                        return
                except (ValidationError, json.JSONDecodeError):
                    await send(
                        socket,
                        {
                            "type": "error",
                            "id": request_id,
                            "error": {
                                "code": "invalid_input",
                                "message": "Check the request fields",
                                "retryable": False,
                            },
                        },
                    )
                except IntegrityError:
                    await send(
                        socket,
                        {
                            "type": "error",
                            "id": request_id,
                            "error": {
                                "code": "conflict",
                                "message": "Concurrent change; retry the same intent",
                                "retryable": True,
                            },
                        },
                    )
                except AppError as exc:
                    await send(
                        socket,
                        {
                            "type": "error",
                            "id": request_id,
                            "error": {**exc.as_dict(), "retryable": exc.status in {429, 503}},
                        },
                    )
                    if exc.status == 401:
                        await socket.close(code=1008)
                        return
                if not token and time.monotonic() >= deadline:
                    await socket.close(code=1008)
                    return
        except AppError as exc:
            await send(
                socket,
                {"type": "error", "id": None, "error": {**exc.as_dict(), "retryable": False}},
            )
            await socket.close(code=1008)
        except (WebSocketDisconnect, TimeoutError, RuntimeError):
            pass
        finally:
            if receive_task is not None:
                receive_task.cancel()
                await asyncio.gather(receive_task, return_exceptions=True)
            peers.pop(socket, None)
            if account:
                connections[account] -= 1
                if not connections[account]:
                    del connections[account]

    return routes
