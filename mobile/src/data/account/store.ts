import type { AccountData, Intent, Profile } from "./contracts.ts";

export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}
// Every update commits one account document atomically. No tokens, contact aliases,
// device display choices, or fixtures ever enter this projection.
export class AccountStore {
  private writes: Promise<unknown> = Promise.resolve();
  private storage: KeyValueStore;
  constructor(storage: KeyValueStore) {
    this.storage = storage;
  }
  async installation(id: () => string) {
    const existing = await this.storage.get("installation");
    if (existing) return existing;
    const value = id();
    await this.storage.set("installation", value);
    return value;
  }
  async read(user: string): Promise<AccountData | null> {
    await this.writes;
    const value = await this.storage.get(`account:${user}`);
    return value ? JSON.parse(value) : null;
  }
  private update(
    user: string,
    edit: (current: AccountData | null) => AccountData,
  ) {
    const next = this.writes.then(async () => {
      const value = await this.storage.get(`account:${user}`);
      await this.storage.set(
        `account:${user}`,
        JSON.stringify(edit(value ? JSON.parse(value) : null)),
      );
    });
    this.writes = next.catch(() => {});
    return next;
  }
  saveProfile(value: Profile) {
    return this.update(value.id, (current) => ({
      profile:
        current && current.profile.version > value.version
          ? current.profile
          : value,
      outbox: current?.outbox ?? [],
    }));
  }
  enqueue(user: string, intent: Intent) {
    return this.update(user, (current) => {
      if (!current) throw new Error("Load your profile first");
      if (current.outbox.length)
        throw new Error("Resolve the pending edit first");
      return { ...current, outbox: [intent] };
    });
  }
  finish(user: string, action: string, value: Profile) {
    return this.update(user, (current) => {
      if (!current) throw new Error("Account cache is missing");
      return {
        profile:
          current.profile.version > value.version ? current.profile : value,
        outbox: current.outbox.filter((i) => i.action_id !== action),
      };
    });
  }
  mark(user: string, action: string, state: Intent["state"], error: string) {
    return this.update(user, (current) => {
      if (!current) throw new Error("Account cache is missing");
      return {
        ...current,
        outbox: current.outbox.map((i) =>
          i.action_id === action ? { ...i, state, error } : i,
        ),
      };
    });
  }
  discard(user: string) {
    return this.update(user, (current) => {
      if (!current) throw new Error("Account cache is missing");
      return { ...current, outbox: [] };
    });
  }
}
