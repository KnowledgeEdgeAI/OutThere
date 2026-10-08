import {
  RequestError,
  profile,
  session,
  type AccountData,
  type Device,
  type Session,
} from "./contracts.ts";
import { AccountSocket } from "./socket.ts";
import { AccountStore, type KeyValueStore } from "./store.ts";

export interface AccountView {
  status: "signed_out" | "connecting" | "ready" | "offline" | "reauth_required";
  data: AccountData | null;
  devices: Device[];
  error: string | null;
}
export class AccountClient {
  private socket: AccountSocket;
  private store: AccountStore;
  private secrets: KeyValueStore;
  private id: () => string;
  private platform: "ios" | "android" | "web";
  private view: AccountView = {
    status: "signed_out",
    data: null,
    devices: [],
    error: null,
  };
  private listeners = new Set<() => void>();
  private credentials: Session | null = null;
  private installation = "";
  private active = true;
  private busy: Promise<void> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private reconnect: ReturnType<typeof setTimeout> | null = null;
  private retry = 0;
  private generation = 0;
  constructor(
    socket: AccountSocket,
    store: AccountStore,
    secrets: KeyValueStore,
    id: () => string,
    platform: "ios" | "android" | "web",
  ) {
    this.socket = socket;
    this.store = store;
    this.secrets = secrets;
    this.id = id;
    this.platform = platform;
    socket.onClose = () => {
      if (this.credentials && this.active) this.goOffline();
    };
    socket.onAuthError = () => {
      void this.connect();
    };
    socket.onProfile = (value) => {
      const generation = this.generation;
      void this.receive(value, generation).catch((e) =>
        this.update({ error: this.message(e) }),
      );
    };
  }
  getSnapshot = () => this.view;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private update(change: Partial<AccountView>) {
    this.view = { ...this.view, ...change };
    this.listeners.forEach((listener) => listener());
  }
  private message(error: unknown) {
    return error instanceof Error ? error.message : "Please try again";
  }
  async initialize() {
    this.active = true;
    try {
      this.installation = await this.store.installation(this.id);
      const saved = await this.secrets.get("account-session");
      if (saved) {
        const value = JSON.parse(saved) as Session;
        // Keychain may survive reinstall; the database's installation marker must match.
        if (value.installation_id !== this.installation)
          await this.secrets.remove("account-session");
        else {
          this.credentials = value;
          this.update({
            data: await this.store.read(value.user_id),
            status: "offline",
          });
          await this.connect();
        }
      }
    } catch (error) {
      this.update({ error: this.message(error), status: "signed_out" });
    }
  }

  private async save(value: Session) {
    await this.secrets.set("account-session", JSON.stringify(value));
    this.credentials = value;
  }
  private async receive(value: unknown, generation: number) {
    const p = profile(value);
    if (generation !== this.generation || p.id !== this.credentials?.user_id)
      return;
    await this.store.saveProfile(p);
    if (generation === this.generation)
      this.update({ data: await this.store.read(p.id) });
  }
  async login(phone: string, name: string) {
    if (this.busy || this.view.status === "connecting")
      throw new Error("Please wait for sign-in");
    if (this.credentials) throw new Error("Sign out before switching accounts");
    this.update({ status: "connecting", error: null, data: null, devices: [] });
    this.socket.close();
    try {
      if (!this.installation)
        this.installation = await this.store.installation(this.id);
      await this.socket.open();
      const value = await this.socket.request<{ profile: unknown }>(
        "auth.login",
        "command",
        {
          phone,
          name: name.trim() || null,
          installation_id: this.installation,
          platform: this.platform,
        },
      );
      await this.save(session(value, this.installation));
      await this.receive(value.profile, this.generation);
      await this.ready();
    } catch (error) {
      this.socket.close();
      this.update({
        status: this.credentials ? "offline" : "signed_out",
        error: this.message(error),
      });
      throw error;
    }
  }
  async connect(): Promise<void> {
    if (this.busy) return this.busy;
    if (!this.credentials || !this.active) return;
    this.busy = this.connectOnce().finally(() => {
      this.busy = null;
    });
    return this.busy;
  }
  private async connectOnce() {
    const generation = this.generation;
    this.update({ status: "connecting", error: null });
    this.clearTimers();
    this.socket.close();
    try {
      await this.socket.open();
      const credentials = this.credentials!;
      if (
        credentials.renewal_id ||
        credentials.access_expires_at < Date.now() / 1000 + 60
      ) {
        await this.renew();
      } else {
        try {
          await this.socket.request("auth.resume", "query", {
            access_token: credentials.access_token,
            device_id: credentials.device_id,
          });
        } catch (error) {
          if (
            !(error instanceof RequestError) ||
            error.code !== "unauthenticated"
          )
            throw error;
          this.socket.close();
          await this.socket.open();
          await this.renew();
        }
      }
      if (!this.active || generation !== this.generation) return;
      await this.receive(
        await this.socket.request("profile.get", "query"),
        generation,
      );
      await this.ready();
    } catch (error) {
      if (error instanceof RequestError && error.code === "unauthenticated") {
        this.generation++;
        this.credentials = null;
        this.clearTimers();
        this.socket.close();
        await this.secrets.remove("account-session");
        this.update({
          status: "reauth_required",
          data: null,
          devices: [],
          error: "Sign in again to continue",
        });
      } else this.goOffline(this.message(error));
    }
  }
  private async renew() {
    const current = this.credentials!;
    if (!current.renewal_id)
      await this.save({ ...current, renewal_id: this.id() });
    const pending = this.credentials!;
    const value = await this.socket.request<Session>(
      "auth.refresh",
      "command",
      {
        refresh_token: pending.refresh_token,
        device_id: pending.device_id,
        renewal_id: pending.renewal_id,
      },
    );
    // Persist the new pair before clearing the saved renewal intent.
    await this.save(session(value, this.installation));
  }
  private async ready() {
    this.retry = 0;
    this.update({ status: "ready", error: null });
    await this.loadDevices();
    await this.drain();
    this.heartbeat = setInterval(() => {
      if (this.busy) return;
      if (
        this.credentials &&
        this.credentials.access_expires_at < Date.now() / 1000 + 60
      ) {
        void this.connect();
        return;
      }
      void this.socket.request("ping", "query").catch(() => this.goOffline());
      void this.drain().catch((e) => this.update({ error: this.message(e) }));
    }, 25000);
  }
  private goOffline(
    error = "Waiting to reconnect. Your pending edit stays on this device.",
  ) {
    this.clearTimers();
    this.socket.close();
    this.update({ status: "offline", error });
    if (!this.active || !this.credentials) return;
    const delay =
      Math.min(30000, 1000 * 2 ** this.retry++) * (0.8 + Math.random() * 0.4);
    this.reconnect = setTimeout(() => {
      void this.connect();
    }, delay);
  }
  private clearTimers() {
    if (this.heartbeat) clearInterval(this.heartbeat);
    if (this.reconnect) clearTimeout(this.reconnect);
    this.heartbeat = this.reconnect = null;
  }
  setActive(active: boolean) {
    this.active = active;
    if (active) void this.connect();
    else {
      this.clearTimers();
      this.socket.close();
      if (this.credentials) this.update({ status: "offline", error: null });
    }
  }
  async editName(name: string) {
    const user = this.credentials?.user_id;
    if (!user || !this.view.data) throw new Error("Sign in first");
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 80)
      throw new Error("Enter a name of 1–80 characters");
    await this.store.enqueue(user, {
      action_id: this.id(),
      issued_at: new Date().toISOString(),
      name: "profile.update",
      payload: {
        name: trimmed,
        expected_version: this.view.data.profile.version,
      },
      state: "queued",
    });
    this.update({ data: await this.store.read(user), error: null });
    await this.drain();
  }
  private draining = false;
  async drain() {
    const user = this.credentials?.user_id;
    if (!user || this.view.status !== "ready" || this.draining) return;
    this.draining = true;
    const generation = this.generation;
    try {
      const data = await this.store.read(user);
      for (const intent of data?.outbox ?? []) {
        if (intent.state !== "queued" || generation !== this.generation)
          continue;
        if (Date.parse(intent.issued_at) < Date.now() - 7 * 86400000) {
          await this.store.mark(
            user,
            intent.action_id,
            "expired",
            "Edit expired; refresh and review",
          );
          continue;
        }
        try {
          const result = profile(
            await this.socket.request(
              intent.name,
              "command",
              intent.payload,
              intent,
            ),
          );
          if (result.id !== user) throw new Error("Account mismatch");
          await this.store.finish(user, intent.action_id, result);
        } catch (error) {
          if (!(error instanceof RequestError) || error.retryable) throw error;
          if (error.code === "unauthenticated") {
            void this.connect();
            break;
          }
          await this.store.mark(
            user,
            intent.action_id,
            error.code === "expired" ? "expired" : "needs_review",
            error.message,
          );
          await this.receive(
            await this.socket.request("profile.get", "query"),
            generation,
          );
        }
      }
      if (generation === this.generation)
        this.update({ data: await this.store.read(user) });
    } catch (error) {
      if (generation === this.generation) this.goOffline(this.message(error));
    } finally {
      this.draining = false;
    }
  }
  async discardEdit() {
    const user = this.credentials?.user_id;
    if (!user) return;
    await this.store.discard(user);
    this.update({ data: await this.store.read(user), error: null });
  }
  async loadDevices() {
    const value = await this.socket.request<{ items: Device[] }>(
      "device.list",
      "query",
    );
    this.update({ devices: value.items });
  }
  async revoke(device: string) {
    await this.socket.request(
      "device.revoke",
      "command",
      { device_id: device },
      {
        action_id: this.id(),
        issued_at: new Date().toISOString(),
      },
    );
    if (device === this.credentials?.device_id) await this.clearSession();
    else await this.loadDevices();
  }
  async signOut() {
    // Require server acknowledgement; an offline button must not claim revocation.
    await this.socket.request("auth.logout", "command");
    await this.clearSession();
  }
  private async clearSession() {
    this.generation++;
    this.credentials = null;
    this.clearTimers();
    this.socket.close();
    await this.secrets.remove("account-session");
    this.update({ status: "signed_out", data: null, devices: [], error: null });
  }
  dispose() {
    this.generation++;
    this.active = false;
    this.clearTimers();
    this.socket.close();
  }
}
