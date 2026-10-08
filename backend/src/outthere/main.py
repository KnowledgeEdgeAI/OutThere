import asyncio
import json
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlmodel import select

from outthere import auth, media, service, v2
from outthere.contracts import Authenticate, Envelope, Exchange, PlacesSearch, Refresh
from outthere.db import make_engine, transaction
from outthere.errors import AppError
from outthere.integrations.places import make_places
from outthere.models import User
from outthere.settings import Settings

logger = logging.getLogger(__name__)
bearer = HTTPBearer()


def access_token(value: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]) -> str:
    return value.credentials


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    places = make_places(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="OutThere", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.include_router(v2.router(engine, settings))
    app.include_router(media.routes(engine, settings))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content={"error": exc.as_dict()})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_payload", "message": "Check the request fields"}},
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/health")
    def health():
        with transaction(engine) as db:
            db.exec(select(User.id).limit(1)).all()
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/v1/auth/exchange")
    def exchange(payload: Exchange, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return auth.exchange(engine, settings, payload)

    @app.post("/v1/auth/refresh")
    def refresh(payload: Refresh, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return auth.refresh(engine, settings, payload.refresh_token)

    @app.post("/v1/auth/logout", status_code=204)
    def logout(token: Annotated[str, Depends(access_token)]):
        auth.logout(engine, token)
        return Response(status_code=204)

    def check_auth(token: str) -> str:
        with transaction(engine) as db:
            return str(auth.authenticate(db, token).user_id)

    async def send(socket: WebSocket, data: dict):
        await asyncio.wait_for(socket.send_json(data), timeout=5)

    @app.websocket("/v1/ws")
    async def websocket(socket: WebSocket):
        origin = socket.headers.get("origin")
        if origin is not None and origin not in settings.allowed_origins:
            await socket.close(code=1008)
            return
        await socket.accept()
        receive_task = None
        try:
            raw = await asyncio.wait_for(socket.receive_text(), timeout=10)
            if len(raw.encode()) > 4096:
                raise AppError("invalid_auth", "Authentication frame is too large", 401)
            hello = Authenticate.model_validate_json(raw)
            user_id = await run_in_threadpool(check_auth, hello.access_token)
            cursor = hello.cursor
            await send(socket, {"type": "ready", "user_id": user_id})
            rate_window = deque()
            while True:
                # Replay and live delivery use exactly the same durable, authorized feed.
                batch = await run_in_threadpool(service.changes, engine, hello.access_token, cursor)
                if batch["cursor"] != cursor:
                    await send(socket, batch)
                    cursor = batch["cursor"]
                try:
                    if receive_task is None:
                        receive_task = asyncio.create_task(socket.receive_text())
                    raw = await asyncio.wait_for(
                        asyncio.shield(receive_task),
                        timeout=0.01 if batch["has_more"] else settings.sync_poll_seconds,
                    )
                except TimeoutError:
                    continue
                receive_task = None
                request_id = None
                try:
                    if len(raw.encode()) > 16_384:
                        raise AppError("too_large", "Command frame exceeds 16 KiB", 413)
                    request = Envelope.model_validate_json(raw)
                    request_id = str(request.id)
                    tick = time.monotonic()
                    while rate_window and tick - rate_window[0] > 10:
                        rate_window.popleft()
                    if len(rate_window) >= 60:
                        raise AppError("rate_limited", "Slow down and retry shortly", 429)
                    rate_window.append(tick)
                    if request.type == "ping":
                        result = {"pong": True}
                    elif request.type == "command":
                        result = await run_in_threadpool(
                            service.command,
                            engine,
                            hello.access_token,
                            request,
                        )
                    elif request.name == "places.search":
                        await run_in_threadpool(check_auth, hello.access_token)
                        payload = service.validate(PlacesSearch, request.payload)
                        result = {"items": await run_in_threadpool(places.search, payload.query)}
                    else:
                        result = await run_in_threadpool(
                            service.query,
                            engine,
                            hello.access_token,
                            request,
                        )
                    await send(socket, {"type": "result", "id": request_id, "data": result})
                except (ValidationError, json.JSONDecodeError):
                    await send(
                        socket,
                        {
                            "type": "error",
                            "id": request_id,
                            "error": {
                                "code": "invalid_payload",
                                "message": "Invalid request envelope",
                            },
                        },
                    )
                except AppError as exc:
                    await send(socket, {"type": "error", "id": request_id, "error": exc.as_dict()})
                    if exc.status == 401:
                        await socket.close(code=1008)
                        return
        except AppError as exc:
            await send(socket, {"type": "error", "error": exc.as_dict()})
            await socket.close(code=1008)
        except (ValidationError, json.JSONDecodeError):
            await socket.close(code=1008)
        except TimeoutError:
            await socket.close(code=1013)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("WebSocket request failed")
            await socket.close(code=1011)
        finally:
            if receive_task is not None:
                receive_task.cancel()
                await asyncio.gather(receive_task, return_exceptions=True)

    return app


app = create_app()
