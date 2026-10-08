import type { KeyValueStore } from "./store";

let database: Promise<IDBDatabase> | null = null;
function open(): Promise<IDBDatabase> {
  if (!database)
    database = new Promise((resolve, reject) => {
      const request = indexedDB.open("outthere-account", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("cache");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error("Local storage is unavailable"));
    });
  return database;
}
async function operation(
  key: string,
  value?: string,
  remove = false,
): Promise<string | null> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(
      "cache",
      value !== undefined || remove ? "readwrite" : "readonly",
    );
    const store = transaction.objectStore("cache");
    const request = remove
      ? store.delete(key)
      : value !== undefined
        ? store.put(value, key)
        : store.get(key);
    transaction.oncomplete = () =>
      resolve(typeof request.result === "string" ? request.result : null);
    transaction.onerror = transaction.onabort = () =>
      reject(new Error("Could not save local data"));
  });
}
export const cache: KeyValueStore = {
  get: (key) => operation(key),
  set: async (key, value) => {
    await operation(key, value);
  },
  remove: async (key) => {
    await operation(key, undefined, true);
  },
};
// Browser preview credentials stay in memory. Native builds use SecureStore.
const memory = new Map<string, string>();
export const secrets: KeyValueStore = {
  get: async (key) => memory.get(key) ?? null,
  set: async (key, value) => {
    memory.set(key, value);
  },
  remove: async (key) => {
    memory.delete(key);
  },
};
