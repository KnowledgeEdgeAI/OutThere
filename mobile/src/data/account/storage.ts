import * as SQLite from "expo-sqlite";
import * as SecureStore from "expo-secure-store";
import type { KeyValueStore } from "./store";

let database: Promise<SQLite.SQLiteDatabase> | null = null;
function open() {
  if (!database)
    database = SQLite.openDatabaseAsync("outthere-account.db").then(
      async (db) => {
        await db.execAsync(
          "PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        );
        return db;
      },
    );
  return database;
}
export const cache: KeyValueStore = {
  async get(key) {
    const row = await (
      await open()
    ).getFirstAsync<{ value: string }>(
      "SELECT value FROM cache WHERE key=?",
      key,
    );
    return row?.value ?? null;
  },
  async set(key, value) {
    await (
      await open()
    ).runAsync(
      "INSERT INTO cache(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
      key,
      value,
    );
  },
  async remove(key) {
    await (await open()).runAsync("DELETE FROM cache WHERE key=?", key);
  },
};
const options = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};
export const secrets: KeyValueStore = {
  get: (key) => SecureStore.getItemAsync(key, options),
  set: (key, value) => SecureStore.setItemAsync(key, value, options),
  remove: (key) => SecureStore.deleteItemAsync(key, options),
};
