"""Private album metadata and bounded capability-based local file transfers."""

import hashlib
import secrets
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import delete
from sqlmodel import Field as DBField
from sqlmodel import SQLModel, select

from outthere.contracts import Input
from outthere.db import transaction
from outthere.errors import AppError
from outthere.events import emit
from outthere.models import Participant, Plan, now
from outthere.product import missing, plan_access, version


class Media(SQLModel, table=True):
    id: UUID = DBField(primary_key=True)
    uploader_id: UUID = DBField(foreign_key="user.id", index=True)
    plan_id: UUID | None = DBField(default=None, foreign_key="plan.id", index=True)
    room_id: UUID | None = DBField(default=None, index=True)
    purpose: str
    mime: str
    byte_size: int
    checksum: str
    state: str = "prepared"
    expires_at: int | None = DBField(default=None, index=True)
    accepted_at: int | None = None
    upload_hash: str
    upload_expires_at: int


class Album(SQLModel, table=True):
    id: UUID = DBField(primary_key=True)
    plan_id: UUID = DBField(foreign_key="plan.id", index=True)
    creator_id: UUID = DBField(foreign_key="user.id")
    title: str
    state: str = "active"
    version: int = 1


class AlbumGrant(SQLModel, table=True):
    album_id: UUID = DBField(foreign_key="album.id", primary_key=True)
    user_id: UUID = DBField(foreign_key="user.id", primary_key=True, index=True)


class AlbumMedia(SQLModel, table=True):
    album_id: UUID = DBField(foreign_key="album.id", primary_key=True)
    media_id: UUID = DBField(foreign_key="media.id", primary_key=True)
    added_by: UUID = DBField(foreign_key="user.id")
    hidden_at: int | None = None


class DownloadGrant(SQLModel, table=True):
    token_hash: str = DBField(primary_key=True)
    media_id: UUID = DBField(foreign_key="media.id", index=True)
    user_id: UUID = DBField(foreign_key="user.id")
    device_id: UUID = DBField(foreign_key="device.id")
    variant: str = "original"
    expires_at: int = DBField(index=True)


class MediaShare(SQLModel, table=True):
    id: UUID = DBField(default_factory=uuid4, primary_key=True)
    owner_id: UUID = DBField(foreign_key="user.id")
    media_id: UUID = DBField(foreign_key="media.id", index=True)
    album_id: UUID = DBField(foreign_key="album.id")
    token_hash: str = DBField(unique=True, index=True)
    expires_at: int = DBField(index=True)
    revoked_at: int | None = None


class PlanId(Input):
    plan_id: UUID


class AlbumId(Input):
    album_id: UUID


class AlbumCreate(PlanId):
    album_id: UUID
    title: str = Field(min_length=1, max_length=100)


class AlbumEdit(AlbumId):
    expected_version: int = Field(ge=1)


class AlbumUpdate(AlbumEdit):
    title: str = Field(min_length=1, max_length=100)


class MediaId(Input):
    media_id: UUID


class Read(MediaId):
    variant: str = Field(default="original", pattern=r"^(original|thumbnail)$")


class Prepare(MediaId):
    plan_id: UUID | None = None
    room_id: UUID | None = None
    purpose: str = Field(pattern=r"^(album|chat|profile)$")
    mime: str = Field(pattern=r"^(image/(jpeg|png|webp)|audio/(wav|mp4)|video/mp4)$")
    byte_size: int = Field(gt=0, le=50 * 1024 * 1024)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class AlbumItem(AlbumEdit, MediaId):
    pass


class Promote(MediaId, AlbumId):
    pass


class List(PlanId):
    after: UUID | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ShareCreate(MediaId, AlbumId):
    expires_in_seconds: int = Field(default=3600, ge=60, le=86400)


class ShareRevoke(Input):
    share_id: UUID


CONTRACTS = {
    "album.list": ("query", List),
    "album.get": ("query", AlbumId),
    "album.create": ("command", AlbumCreate),
    "album.update": ("command", AlbumUpdate),
    "album.delete": ("command", AlbumEdit),
    "album.media.add": ("command", AlbumItem),
    "album.media.remove": ("command", AlbumItem),
    "album.media.hide": ("command", AlbumItem),
    "media.prepare": ("command", Prepare),
    "media.complete": ("command", MediaId),
    "media.abort": ("command", MediaId),
    "media.read": ("query", Read),
    "media.share.create": ("command", ShareCreate),
    "media.share.revoke": ("command", ShareRevoke),
    "media.promote": ("command", Promote),
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def object_path(settings, media_id, variant="original"):
    if variant == "thumbnail":
        return Path(settings.media_directory).resolve() / f"{media_id}.thumbnail.png"
    return Path(settings.media_directory).resolve() / f"{media_id}.bin"


def allowed(db, user_id, row):
    from outthere.safety import blocked

    if blocked(db, user_id, row.uploader_id):
        return False
    if row.state != "ready" or (row.expires_at is not None and row.expires_at <= now()):
        return False
    if row.uploader_id == user_id:
        return True
    from outthere.models import User

    owner = db.get(User, row.uploader_id)
    if owner.dp_media_id == row.id:
        from outthere.sessions import related_profile

        try:
            related_profile(db, user_id, owner.id)
            return True
        except AppError:
            return False
    from outthere.delivery import AttachmentTarget, permitted
    from outthere.models import Device

    attachment = db.exec(
        select(AttachmentTarget)
        .join(Device)
        .where(
            AttachmentTarget.media_id == row.id,
            Device.user_id == user_id,
            Device.revoked_at.is_(None),
            AttachmentTarget.expires_at > now(),
            AttachmentTarget.downloaded_at.is_(None),
        )
    ).first()
    if attachment and permitted(db, user_id, row.room_id):
        return True
    return (
        db.exec(
            select(AlbumGrant)
            .join(Album)
            .join(AlbumMedia)
            .where(
                AlbumGrant.user_id == user_id,
                AlbumMedia.media_id == row.id,
                AlbumMedia.hidden_at.is_(None),
                Album.state == "active",
            )
        ).first()
        is not None
    )


def album_access(db, user_id, album_id, edit=False):
    from outthere.safety import blocked

    album = db.get(Album, album_id)
    if album is None or album.state != "active" or not db.get(AlbumGrant, (album_id, user_id)):
        missing("Album")
    if blocked(db, user_id, album.creator_id):
        missing("Album")
    if edit and user_id not in {album.creator_id, db.get(Plan, album.plan_id).host_id}:
        raise AppError("forbidden", "Only album creator or plan host can edit", 403)
    return album


def album_view(db, album, viewer=None):
    from outthere.safety import blocked

    rows = db.exec(
        select(AlbumMedia)
        .where(AlbumMedia.album_id == album.id, AlbumMedia.hidden_at.is_(None))
        .order_by(AlbumMedia.media_id)
    ).all()
    return {
        "id": str(album.id),
        "plan_id": str(album.plan_id),
        "title": album.title,
        "version": album.version,
        "media": [
            metadata(db.get(Media, r.media_id))
            for r in rows
            if viewer is None or not blocked(db, viewer, db.get(Media, r.media_id).uploader_id)
        ],
    }


def metadata(row):
    return {
        "id": str(row.id),
        "mime": row.mime,
        "byte_size": row.byte_size,
        "checksum": row.checksum,
        "state": row.state,
    }


def emit_album(db, album):
    users = set(db.exec(select(AlbumGrant.user_id).where(AlbumGrant.album_id == album.id)).all())
    emit(db, users, "v2.album", album.id)


def grant_attendance(db, plan_id, user_id):
    for album in db.exec(
        select(Album).where(Album.plan_id == plan_id, Album.state == "active")
    ).all():
        if db.get(AlbumGrant, (album.id, user_id)) is None:
            db.add(AlbumGrant(album_id=album.id, user_id=user_id))
            emit(db, {user_id}, "v2.album", album.id)


def revoke_attendance(db, plan_id, user_id):
    for album in db.exec(select(Album).where(Album.plan_id == plan_id)).all():
        grant = db.get(AlbumGrant, (album.id, user_id))
        if grant:
            db.delete(grant)
            emit(db, {user_id}, "v2.album", album.id)


def handle(db, settings, user, device, name, data):
    if name == "media.share.revoke":
        share = db.get(MediaShare, data.share_id)
        if share is None or share.owner_id != user.id:
            missing("Share")
        share.revoked_at = now()
        return {"revoked": True}
    if name == "media.share.create":
        album_access(db, user.id, data.album_id)
        link = db.get(AlbumMedia, (data.album_id, data.media_id))
        media = db.get(Media, data.media_id)
        if not link or link.hidden_at is not None or not media or not allowed(db, user.id, media):
            missing("Media")
        token = secrets.token_urlsafe(32)
        share = MediaShare(
            owner_id=user.id,
            media_id=media.id,
            album_id=data.album_id,
            token_hash=digest(token),
            expires_at=now() + data.expires_in_seconds,
        )
        db.add(share)
        return {
            "share_id": str(share.id),
            "download_url": f"/v2/shared-files/{media.id}?token={token}",
            "expires_at": share.expires_at,
        }
    if name == "album.list":
        from sqlalchemy import and_, or_

        from outthere.safety import Block

        statement = (
            select(Album)
            .join(AlbumGrant)
            .where(
                Album.plan_id == data.plan_id,
                AlbumGrant.user_id == user.id,
                Album.state == "active",
                ~select(Block)
                .where(
                    or_(
                        and_(Block.blocker_id == user.id, Block.blocked_id == Album.creator_id),
                        and_(Block.blocked_id == user.id, Block.blocker_id == Album.creator_id),
                    )
                )
                .exists(),
            )
        )
        if data.after:
            statement = statement.where(Album.id > data.after)
        rows = db.exec(statement.order_by(Album.id).limit(data.limit + 1)).all()
        return {
            "items": [album_view(db, a, user.id) for a in rows[: data.limit]],
            "next_after": str(rows[data.limit - 1].id) if len(rows) > data.limit else None,
        }
    if name == "album.get":
        return album_view(db, album_access(db, user.id, data.album_id), user.id)
    if name == "album.create":
        plan = plan_access(db, user.id, data.plan_id)
        if db.get(Participant, (plan.id, user.id)).rsvp != "in":
            raise AppError("forbidden", "Accept attendance before creating an album", 403)
        if db.get(Album, data.album_id):
            raise AppError("action_conflict", "Album ID already exists", 409)
        album = Album(id=data.album_id, plan_id=plan.id, creator_id=user.id, title=data.title)
        db.add(album)
        db.flush()
        for p in db.exec(
            select(Participant).where(Participant.plan_id == plan.id, Participant.rsvp == "in")
        ).all():
            db.add(AlbumGrant(album_id=album.id, user_id=p.user_id))
        db.flush()
        emit_album(db, album)
        return album_view(db, album, user.id)
    if name in {"media.promote", "album.media.add"}:
        album = album_access(db, user.id, data.album_id)
        row = db.get(Media, data.media_id)
        if row is None or row.plan_id != album.plan_id or not allowed(db, user.id, row):
            missing("Media")
        if row.uploader_id != user.id:
            raise AppError("forbidden", "Only uploader can save media", 403)
        if name == "album.media.add":
            version(album, data.expected_version)
        existing = db.get(AlbumMedia, (album.id, row.id))
        if existing is None:
            db.add(AlbumMedia(album_id=album.id, media_id=row.id, added_by=user.id))
            album.version += 1
        else:
            existing.hidden_at = None
        row.expires_at = None
        db.flush()
        emit_album(db, album)
        return album_view(db, album, user.id)
    if name.startswith("album."):
        album = album_access(db, user.id, data.album_id, edit=True)
        version(album, data.expected_version)
        if name == "album.update":
            album.title = data.title
        elif name == "album.delete":
            album.state = "deleted"
        else:
            item = db.get(AlbumMedia, (album.id, data.media_id))
            if item is None:
                missing("Album media")
            if name.endswith("remove"):
                db.delete(item)
            else:
                item.hidden_at = now()
        album.version += 1
        db.flush()
        emit_album(db, album)
        return {"album_id": str(album.id), "version": album.version, "state": album.state}
    if name == "media.prepare":
        if data.purpose == "profile":
            if data.plan_id is not None or not data.mime.startswith("image/"):
                raise AppError("invalid_input", "Profile media must be an image without a plan")
        elif data.purpose == "chat":
            from outthere.delivery import room_access

            if (data.plan_id is None) == (data.room_id is None):
                raise AppError("invalid_input", "Supply one chat parent")
            room_access(db, user.id, data.plan_id or data.room_id, write=True)
        else:
            if data.plan_id is None or data.room_id is not None:
                raise AppError("invalid_input", "Plan is required")
            plan_access(db, user.id, data.plan_id)
        if db.get(Media, data.media_id):
            raise AppError("action_conflict", "Media ID already exists", 409)
        if data.mime.startswith("image/") and data.byte_size > 10 * 1024 * 1024:
            raise AppError("invalid_input", "Images must be at most 10 MiB")
        token = secrets.token_urlsafe(32)
        row = Media(
            id=data.media_id,
            uploader_id=user.id,
            plan_id=data.plan_id,
            room_id=data.room_id or data.plan_id,
            purpose=data.purpose,
            mime=data.mime,
            byte_size=data.byte_size,
            checksum=data.checksum,
            upload_hash=digest(token),
            upload_expires_at=now() + 900,
            expires_at=now() + 7 * 86400,
        )
        db.add(row)
        return {
            "media_id": str(row.id),
            "upload_url": f"/v2/files/{row.id}?token={token}",
            "expires_at": row.upload_expires_at,
        }
    row = db.get(Media, data.media_id)
    if row is None:
        missing("Media")
    if name == "media.read":
        if not allowed(db, user.id, row):
            missing("Media")
        if data.variant == "thumbnail" and not row.mime.startswith("image/"):
            raise AppError("invalid_input", "This file has no thumbnail")
        token = secrets.token_urlsafe(32)
        db.add(
            DownloadGrant(
                token_hash=digest(token),
                variant=data.variant,
                media_id=row.id,
                user_id=user.id,
                device_id=device.id,
                expires_at=now() + 120,
            )
        )
        return {
            "media_id": str(row.id),
            "download_url": f"/v2/files/{row.id}?token={token}",
            "expires_at": now() + 120,
        }
    if row.uploader_id != user.id:
        missing("Media")
    if name == "media.abort":
        if db.exec(select(AlbumMedia).where(AlbumMedia.media_id == row.id)).first():
            raise AppError("forbidden", "Saved album media cannot be aborted", 403)
        row.state = "aborted"
    else:
        if (
            row.state not in {"uploaded", "ready"}
            or row.expires_at is None
            or row.expires_at <= now()
        ):
            raise AppError("expired", "Upload is unavailable", 409)
        row.state = "ready"
    return metadata(row)


def mime_matches(mime, prefix):
    if mime == "image/png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return prefix.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP"
    if mime == "audio/wav":
        return prefix[:4] == b"RIFF" and prefix[8:12] == b"WAVE"
    return prefix[4:8] == b"ftyp" and len(prefix) >= 12


def routes(engine, settings):
    router = APIRouter()

    @router.put("/v2/files/{media_id}")
    async def upload(media_id: UUID, request: Request, token: str):
        # Capability only authorizes one bounded object; no account tokens appear in URLs.
        root = Path(settings.media_directory).resolve()
        root.mkdir(parents=True, exist_ok=True)
        temp = root / f"{media_id}.{secrets.token_hex(8)}.upload"
        try:
            with transaction(engine) as db:
                row = db.get(Media, media_id)
                if (
                    row is None
                    or row.upload_hash != digest(token)
                    or row.upload_expires_at <= now()
                    or row.state != "prepared"
                ):
                    missing("Upload")
                size, checksum, mime = row.byte_size, row.checksum, row.mime
            hasher, count, prefix = hashlib.sha256(), 0, b""
            with temp.open("xb") as file:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > size:
                        raise AppError("invalid_input", "Upload exceeds declared size", 413)
                    hasher.update(chunk)
                    if len(prefix) < 32:
                        prefix = (prefix + chunk)[:32]
                    file.write(chunk)
            if count != size or hasher.hexdigest() != checksum or not mime_matches(mime, prefix):
                raise AppError("invalid_input", "Size, checksum or MIME verification failed", 422)
            if mime.startswith("image/"):
                import warnings

                from PIL import Image, UnidentifiedImageError

                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        with Image.open(temp) as image:
                            if image.width * image.height > 16_000_000:
                                raise ValueError("Image dimensions exceed limit")
                            if Image.MIME.get(image.format) != mime:
                                raise ValueError("Image format mismatch")
                            image.verify()
                        with Image.open(temp) as image:
                            image.load()
                except (
                    OSError,
                    ValueError,
                    UnidentifiedImageError,
                    Image.DecompressionBombWarning,
                    Image.DecompressionBombError,
                ) as exc:
                    raise AppError(
                        "invalid_input", "Invalid image or excessive dimensions", 422
                    ) from exc
            with transaction(engine, write=True) as db:
                row = db.exec(select(Media).where(Media.id == media_id).with_for_update()).one()
                if row.state != "prepared" or row.upload_expires_at <= now():
                    raise AppError("expired", "Upload expired", 409)
                if mime.startswith("image/"):
                    with Image.open(temp) as image:
                        image.thumbnail((512, 512))
                        image.convert("RGB").save(
                            object_path(settings, media_id, "thumbnail"), format="PNG"
                        )
                temp.replace(object_path(settings, media_id))
                row.state = "uploaded"
            return {"media_id": str(media_id), "uploaded": True}
        finally:
            temp.unlink(missing_ok=True)

    @router.get("/v2/files/{media_id}")
    def download(media_id: UUID, token: str):
        from outthere.models import Device

        with transaction(engine) as db:
            grant = db.get(DownloadGrant, digest(token))
            row = db.get(Media, media_id)
            if (
                grant is None
                or grant.media_id != media_id
                or grant.expires_at <= now()
                or db.get(Device, grant.device_id).revoked_at is not None
                or row is None
                or not allowed(db, grant.user_id, row)
            ):
                missing("Media")
        path = object_path(settings, media_id, grant.variant)
        if not path.is_file():
            raise AppError("provider_unavailable", "File temporarily unavailable", 503)
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"{media_id}.bin",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.get("/v2/shared-files/{media_id}")
    def shared_download(media_id: UUID, token: str):
        with transaction(engine) as db:
            share = db.exec(
                select(MediaShare).where(MediaShare.token_hash == digest(token))
            ).first()
            row = db.get(Media, media_id)
            if (
                share is None
                or share.media_id != media_id
                or share.revoked_at is not None
                or share.expires_at <= now()
                or row is None
            ):
                missing("Share")
            album_access(db, share.owner_id, share.album_id)
            link = db.get(AlbumMedia, (share.album_id, row.id))
            if not link or link.hidden_at is not None or not allowed(db, share.owner_id, row):
                missing("Share")
        path = object_path(settings, media_id)
        if not path.is_file():
            raise AppError("provider_unavailable", "File temporarily unavailable", 503)
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"{media_id}.bin",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    return router


def cleanup(db, settings):
    db.exec(delete(DownloadGrant).where(DownloadGrant.expires_at <= now()))
    rows = db.exec(select(Media).where(Media.state != "deleted")).all()
    for row in rows:
        saved = db.exec(
            select(AlbumMedia)
            .join(Album)
            .where(AlbumMedia.media_id == row.id, Album.state == "active")
        ).first()
        from outthere.delivery import AttachmentTarget

        waiting = db.exec(
            select(AttachmentTarget).where(
                AttachmentTarget.media_id == row.id,
                AttachmentTarget.downloaded_at.is_(None),
                AttachmentTarget.expires_at > now(),
            )
        ).first()
        completed_chat = row.purpose == "chat" and row.accepted_at is not None and waiting is None
        if not saved and (
            completed_chat
            or row.state == "aborted"
            or (row.expires_at is not None and row.expires_at <= now())
        ):
            row.state = "deleting"
            object_path(settings, row.id).unlink(missing_ok=True)
            object_path(settings, row.id, "thumbnail").unlink(missing_ok=True)
            row.state = "deleted"
