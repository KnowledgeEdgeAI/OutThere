import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { AccountClient } from "../src/data/account/client.ts";
import { AccountSocket } from "../src/data/account/socket.ts";
import { AccountStore } from "../src/data/account/store.ts";
import { RequestError, socketUrl } from "../src/data/account/contracts.ts";

function storage() {
  const values = new Map();
  return {
    values,
    get: async (key) => values.get(key) ?? null,
    set: async (key, value) => {
      values.set(key, value);
    },
    remove: async (key) => {
      values.delete(key);
    },
  };
}
const user = randomUUID(),
  device = randomUUID();
function setup() {
  const cache = storage(),
    vault = storage(),
    store = new AccountStore(cache);
  const current = {
    id: user,
    name: "Planner",
    phone: "+12025550123",
    version: 1,
    phone_verified_at: null,
  };
  const tokens = {
    user_id: user,
    device_id: device,
    access_token: "a".repeat(40),
    refresh_token: "r".repeat(40),
    access_expires_at: Date.now() / 1000 + 900,
    refresh_expires_at: Date.now() / 1000 + 86400,
  };
  const receipts = new Map();
  const socket = {
    connected: false,
    calls: [],
    handler: null,
    onClose() {},
    onProfile() {},
    onAuthError() {},
    async open() {
      this.connected = true;
    },
    close() {
      this.connected = false;
    },
    async request(name, type, payload, intent) {
      this.calls.push({ name, type, payload, intent });
      if (this.handler) {
        const result = await this.handler(name, payload, intent);
        if (result !== undefined) return result;
      }
      if (!this.connected) throw new RequestError("offline", "Offline", true);
      if (name === "auth.login") return { ...tokens, profile: { ...current } };
      if (["auth.resume", "auth.logout", "ping"].includes(name)) return {};
      if (name === "auth.refresh")
        return { ...tokens, access_token: "b".repeat(40) };
      if (name === "profile.get") return { ...current };
      if (name === "device.list") return { items: [] };
      if (name === "profile.update") {
        if (receipts.has(intent.action_id))
          return receipts.get(intent.action_id);
        if (current.version !== payload.expected_version)
          throw new RequestError("version_conflict", "Profile changed");
        current.name = payload.name;
        current.version++;
        const result = { ...current };
        receipts.set(intent.action_id, result);
        return result;
      }
      throw new Error(`Unexpected event ${name}`);
    },
  };
  return {
    cache,
    vault,
    store,
    current,
    tokens,
    socket,
    receipts,
    make: () => new AccountClient(socket, store, vault, randomUUID, "web"),
  };
}

test("offline edit survives restart with the original intent and account isolation", async (t) => {
  const env = setup(),
    client = env.make();
  t.after(() => client.dispose());
  await client.initialize();
  await client.login("+12025550123", "Planner");
  client.setActive(false);
  await client.editName("Updated");
  const saved = (await env.store.read(user)).outbox[0];
  assert.equal(saved.state, "queued");
  assert.equal(env.current.version, 1);
  client.dispose();
  const restarted = env.make();
  t.after(() => restarted.dispose());
  await restarted.initialize();
  assert.equal(restarted.getSnapshot().status, "ready");
  assert.equal(restarted.getSnapshot().data.profile.name, "Updated");
  assert.deepEqual(restarted.getSnapshot().data.outbox, []);
  const sent = env.socket.calls.find((call) => call.name === "profile.update");
  assert.equal(sent.intent.action_id, saved.action_id);
  assert.equal(sent.intent.issued_at, saved.issued_at);
  assert.ok(
    !JSON.stringify([...env.cache.values.values()]).includes("access_token"),
  );
  await env.store.saveProfile({
    ...env.current,
    id: randomUUID(),
    name: "Other account",
  });
  assert.equal((await env.store.read(user)).profile.name, "Updated");
});

test("lost mutation result retries once without a second write", async (t) => {
  const env = setup(),
    client = env.make();
  t.after(() => client.dispose());
  await client.initialize();
  await client.login("+12025550123", "Planner");
  let lose = true;
  env.socket.handler = async (name, payload, intent) => {
    if (name === "profile.update" && lose) {
      lose = false;
      env.current.name = payload.name;
      env.current.version++;
      env.receipts.set(intent.action_id, { ...env.current });
      throw new RequestError("timeout", "Unknown outcome", true);
    }
  };
  await client.editName("Saved once");
  assert.equal(client.getSnapshot().status, "offline");
  assert.equal(client.getSnapshot().data.outbox[0].state, "queued");
  await client.connect();
  assert.equal(env.current.version, 2);
  assert.deepEqual(client.getSnapshot().data.outbox, []);
  const calls = env.socket.calls.filter(
    (call) => call.name === "profile.update",
  );
  assert.equal(calls.length, 2);
  assert.equal(calls[0].intent.action_id, calls[1].intent.action_id);
});

test("conflicts require review and are never silently resubmitted", async (t) => {
  const env = setup(),
    client = env.make();
  t.after(() => client.dispose());
  await client.initialize();
  await client.login("+12025550123", "Planner");
  client.setActive(false);
  await client.editName("Offline edit");
  env.current.name = "Other device";
  env.current.version = 2;
  client.setActive(true);
  await client.connect();
  assert.equal(client.getSnapshot().data.profile.name, "Other device");
  assert.equal(client.getSnapshot().data.outbox[0].state, "needs_review");
  await client.connect();
  assert.equal(
    env.socket.calls.filter((call) => call.name === "profile.update").length,
    1,
  );
  await client.discardEdit();
  assert.deepEqual(client.getSnapshot().data.outbox, []);
});

test("renewal is persisted before sending and reused after lost response", async (t) => {
  const env = setup(),
    client = env.make();
  t.after(() => client.dispose());
  await client.initialize();
  await client.login("+12025550123", "Planner");
  const saved = JSON.parse(await env.vault.get("account-session"));
  saved.access_expires_at = 0;
  await env.vault.set("account-session", JSON.stringify(saved));
  client.dispose();
  let first = true;
  env.socket.handler = async (name) => {
    if (name === "auth.refresh" && first) {
      first = false;
      assert.ok(JSON.parse(await env.vault.get("account-session")).renewal_id);
      throw new RequestError("timeout", "Lost response", true);
    }
  };
  const restarted = env.make();
  t.after(() => restarted.dispose());
  await restarted.initialize();
  assert.equal(restarted.getSnapshot().status, "offline");
  await restarted.connect();
  assert.equal(restarted.getSnapshot().status, "ready");
  const calls = env.socket.calls.filter((call) => call.name === "auth.refresh");
  assert.equal(calls[0].payload.renewal_id, calls[1].payload.renewal_id);
  assert.equal(
    JSON.parse(await env.vault.get("account-session")).renewal_id,
    undefined,
  );
});

test("reinstall rejects surviving secrets and old projections cannot overwrite newer data", async () => {
  const env = setup();
  await env.vault.set(
    "account-session",
    JSON.stringify({ ...env.tokens, installation_id: randomUUID() }),
  );
  const client = env.make();
  await client.initialize();
  client.dispose();
  assert.equal(await env.vault.get("account-session"), null);
  assert.equal(client.getSnapshot().data, null);
  await env.store.saveProfile({ ...env.current, version: 4, name: "Newest" });
  await env.store.saveProfile({ ...env.current, version: 2, name: "Stale" });
  assert.equal((await env.store.read(user)).profile.name, "Newest");
});

test("socket correlates events and results, disconnect keeps outcome unknown", async () => {
  let wire;
  const socket = new AccountSocket(
    "ws://localhost:8000/v2/ws",
    () => {
      wire = {
        readyState: 0,
        onopen: null,
        onclose: null,
        onerror: null,
        onmessage: null,
        sent: [],
        send(value) {
          this.sent.push(JSON.parse(value));
        },
        close() {
          this.readyState = 3;
        },
      };
      queueMicrotask(() => {
        wire.readyState = 1;
        wire.onopen({});
      });
      return wire;
    },
    randomUUID,
    100,
  );
  let received;
  socket.onProfile = (value) => {
    received = value;
  };
  await socket.open();
  const request = socket.request("profile.get", "query");
  wire.onmessage({
    data: JSON.stringify({
      v: 2,
      type: "event",
      name: "profile.changed",
      payload: { version: 3 },
    }),
  });
  wire.onmessage({
    data: JSON.stringify({
      v: 2,
      type: "result",
      id: wire.sent[0].id,
      data: { version: 3 },
    }),
  });
  assert.deepEqual(await request, { version: 3 });
  assert.deepEqual(received, { version: 3 });
  const pending = socket.request(
    "profile.update",
    "command",
    {},
    {
      action_id: randomUUID(),
      issued_at: new Date().toISOString(),
      state: "queued",
      payload: { name: "private" },
    },
  );
  assert.equal(wire.sent[1].state, undefined);
  assert.deepEqual(wire.sent[1].payload, {});
  wire.onclose({});
  await assert.rejects(pending, (e) => e.code === "offline" && e.retryable);
  socket.close();
});

test("server URL rejects remote cleartext and credentials", () => {
  assert.equal(
    socketUrl("ws://127.0.0.1:8000/v2/ws"),
    "ws://127.0.0.1:8000/v2/ws",
  );
  for (const url of [
    "ws://example.com/v2/ws",
    "wss://user:token@example.com/v2/ws",
    "wss://example.com/v2/ws?token=x",
  ])
    assert.throws(() => socketUrl(url));
});
