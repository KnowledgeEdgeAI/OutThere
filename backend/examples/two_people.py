"""Small real-network client. Start the server and create two invitations first."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from getpass import getpass
from uuid import uuid4

import httpx
from websockets.sync.client import connect


class Client:
    def __init__(self, url: str, token: str, cursor: int = 0):
        self.socket = connect(url, open_timeout=5)
        self.cursor = cursor
        self.events = []
        self.socket.send(json.dumps({"type": "auth", "access_token": token, "cursor": cursor}))
        if self.receive()["type"] != "ready":
            raise RuntimeError("Socket authentication failed")

    def receive(self):
        frame = json.loads(self.socket.recv(timeout=10))
        if frame["type"] == "changes":
            # A real frontend stores entities and this cursor together in its local database.
            self.events.extend(frame["events"])
            self.cursor = frame["cursor"]
        return frame

    def command(self, name: str, payload: dict, action_id: str | None = None):
        request_id = str(uuid4())
        self.socket.send(
            json.dumps(
                {
                    "id": request_id,
                    "type": "command",
                    "name": name,
                    "action_id": action_id or str(uuid4()),
                    "payload": payload,
                }
            )
        )
        while True:
            frame = self.receive()
            if frame.get("id") == request_id:
                if frame["type"] == "error":
                    raise RuntimeError(frame["error"]["message"])
                return frame["data"]

    def close(self):
        self.socket.close()


def run(base_url: str, first_invite: str, second_invite: str):
    base_url = base_url.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=10) as http:
        sessions = []
        for name, invite in [("Demo Alice", first_invite), ("Demo Bob", second_invite)]:
            response = http.post(
                "/v1/auth/exchange", json={"invite_token": invite, "display_name": name}
            )
            response.raise_for_status()
            sessions.append(response.json())
        ws_url = base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/v1/ws"
        alice = Client(ws_url, sessions[0]["access_token"])
        bob = Client(ws_url, sessions[1]["access_token"])
        try:
            circle = alice.command("circle.create", {"name": "Demo Sunday crew"})
            alice.command(
                "circle.invite", {"circle_id": circle["id"], "user_id": sessions[1]["user_id"]}
            )
            bob.command("circle.join", {"circle_id": circle["id"]})
            start = datetime.now(UTC) + timedelta(days=2)
            plan = alice.command(
                "plan.create",
                {
                    "title": "Badminton then coffee",
                    "circle_id": circle["id"],
                    "starts_at": start.isoformat(),
                    "ends_at": (start + timedelta(hours=2)).isoformat(),
                    "venue_timezone": "Asia/Kolkata",
                    "place_label": "Community court",
                },
            )
            bob.command("plan.rsvp", {"plan_id": plan["id"], "rsvp": "in", "version": 1})
            cursor = alice.cursor
            alice.close()
            payload = {"plan_id": plan["id"], "body": "See you there!"}
            action_id = str(uuid4())
            message = bob.command("message.send", payload, action_id)
            duplicate = bob.command("message.send", payload, action_id)
            if duplicate != message:
                raise RuntimeError("Retry produced a different result")
            alice = Client(ws_url, sessions[0]["access_token"], cursor)
            while not any(
                event["kind"] == "message.created" and event["data"]["id"] == message["id"]
                for event in alice.events
            ):
                alice.receive()
            print(f"Created circle: {circle['id']}")
            print(f"Created plan:   {plan['id']}")
            print("RSVP saved. One message after retry. Offline message recovered on reconnect.")
        finally:
            alice.close()
            bob.close()
            for session in sessions:
                http.post(
                    "/v1/auth/logout",
                    headers={"Authorization": f"Bearer {session['access_token']}"},
                ).raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    run(args.url, getpass("Alice's invitation: "), getpass("Bob's invitation: "))
