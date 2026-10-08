import argparse
from uuid import UUID

import uvicorn

from outthere.auth import create_invite
from outthere.db import make_engine
from outthere.settings import Settings


def main():
    parser = argparse.ArgumentParser(prog="outthere")
    commands = parser.add_subparsers(dest="command", required=True)
    invite = commands.add_parser("invite", help="Create a one-use beta sign-in invitation")
    invite.add_argument("--user-id", type=UUID, help="Sign into an existing account")
    serve = commands.add_parser("serve", help="Start the API and WebSocket server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    commands.add_parser("worker", help="Run durable background jobs")
    args = parser.parse_args()
    if args.command == "invite":
        engine = make_engine(Settings().database_url)
        try:
            print(create_invite(engine, args.user_id))
        finally:
            engine.dispose()
    elif args.command == "serve":
        uvicorn.run(
            "outthere.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            ws_max_size=65_536,
            ws_max_queue=16,
        )
    else:
        from outthere.worker import main as worker

        worker()


if __name__ == "__main__":
    main()
