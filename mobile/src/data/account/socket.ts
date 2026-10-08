import { RequestError } from "./contracts.ts";

type Listener = (payload: unknown) => void;
export type SocketLike = Pick<
  WebSocket,
  | "readyState"
  | "onopen"
  | "onclose"
  | "onerror"
  | "onmessage"
  | "send"
  | "close"
>;
export class AccountSocket {
  private url: string;
  private makeSocket: (url: string) => SocketLike;
  private id: () => string;
  private timeout: number;
  private socket: SocketLike | null = null;
  private opening: Promise<void> | null = null;
  private pending = new Map<
    string,
    {
      resolve: (v: unknown) => void;
      reject: (e: Error) => void;
      timer: ReturnType<typeof setTimeout>;
    }
  >();
  onProfile: Listener = () => {};
  onClose: () => void = () => {};
  onAuthError: () => void = () => {};
  constructor(
    url: string,
    makeSocket: (url: string) => SocketLike,
    id: () => string,
    timeout = 10000,
  ) {
    this.url = url;
    this.makeSocket = makeSocket;
    this.id = id;
    this.timeout = timeout;
  }
  get connected() {
    return this.socket?.readyState === 1;
  }
  open(): Promise<void> {
    if (this.connected) return Promise.resolve();
    if (this.opening) return this.opening;
    const socket = this.makeSocket(this.url);
    this.socket = socket;
    this.opening = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new RequestError("offline", "Could not reach the server", true));
        socket.close();
      }, this.timeout);
      socket.onopen = () => {
        clearTimeout(timer);
        resolve();
      };
      socket.onerror = () => {
        socket.close();
      };
      socket.onclose = () => {
        clearTimeout(timer);
        if (this.socket !== socket) return;
        this.socket = null;
        reject(new RequestError("offline", "Connection closed", true));
        this.rejectPending();
        this.onClose();
      };
      socket.onmessage = (event) => {
        if (this.socket !== socket) return;
        try {
          const reply = JSON.parse(event.data);
          if (reply.v !== 2) throw new Error("Wrong protocol");
          if (reply.type === "event" && reply.name === "profile.changed") {
            this.onProfile(reply.payload);
            return;
          }
          if (
            reply.type === "error" &&
            reply.error?.code === "unauthenticated" &&
            !reply.id
          ) {
            this.onAuthError();
            return;
          }
          const request = this.pending.get(reply.id);
          if (!request) return;
          clearTimeout(request.timer);
          this.pending.delete(reply.id);
          if (reply.type === "result") request.resolve(reply.data);
          else if (reply.type === "error")
            request.reject(
              new RequestError(
                reply.error.code,
                reply.error.message,
                reply.error.retryable,
              ),
            );
          else
            request.reject(
              new RequestError("invalid_response", "Invalid server response"),
            );
        } catch {
          socket.close();
        }
      };
    }).finally(() => {
      this.opening = null;
    });
    return this.opening;
  }
  request<T>(
    name: string,
    type: "command" | "query",
    payload: object = {},
    intent?: { action_id: string; issued_at: string },
  ): Promise<T> {
    if (!this.connected)
      return Promise.reject(
        new RequestError("offline", "You're offline", true),
      );
    if (this.pending.size >= 20)
      return Promise.reject(
        new RequestError("busy", "Please wait for pending requests", true),
      );
    const id = this.id();
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(
          new RequestError("timeout", "Waiting for server confirmation", true),
        );
      }, this.timeout);
      this.pending.set(id, { resolve: (v) => resolve(v as T), reject, timer });
      try {
        this.socket!.send(
          JSON.stringify({
            v: 2,
            id,
            type,
            name,
            payload,
            ...(intent
              ? { action_id: intent.action_id, issued_at: intent.issued_at }
              : {}),
          }),
        );
      } catch {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(new RequestError("offline", "Connection lost", true));
      }
    });
  }
  private rejectPending() {
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(new RequestError("offline", "Waiting to reconnect", true));
    }
    this.pending.clear();
  }
  close() {
    const socket = this.socket;
    this.socket = null;
    this.rejectPending();
    socket?.close();
  }
}
