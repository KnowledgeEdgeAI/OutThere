export interface Profile {
  id: string;
  name: string;
  phone: string;
  version: number;
  phone_verified_at: null;
}
export interface Session {
  user_id: string;
  device_id: string;
  access_token: string;
  refresh_token: string;
  access_expires_at: number;
  refresh_expires_at: number;
  installation_id: string;
  renewal_id?: string;
}
export interface Device {
  id: string;
  platform: "ios" | "android" | "web";
  last_seen_at: number;
  revoked_at: number | null;
  current: boolean;
}
export interface Intent {
  action_id: string;
  issued_at: string;
  name: "profile.update";
  payload: { name: string; expected_version: number };
  state: "queued" | "needs_review" | "expired";
  error?: string;
}
export interface AccountData {
  profile: Profile;
  outbox: Intent[];
}
export class RequestError extends Error {
  code: string;
  retryable: boolean;
  constructor(code: string, message: string, retryable = false) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function profile(value: unknown): Profile {
  const p = value as Profile | null;
  if (
    !p ||
    !uuid.test(p.id) ||
    typeof p.name !== "string" ||
    typeof p.phone !== "string" ||
    !Number.isInteger(p.version) ||
    p.version < 1 ||
    p.phone_verified_at !== null
  ) {
    throw new RequestError(
      "invalid_response",
      "The server returned an invalid profile",
    );
  }
  return p;
}
export function session(value: unknown, installation: string): Session {
  const p = value as Session | null;
  if (
    !p ||
    !uuid.test(p.user_id) ||
    !uuid.test(p.device_id) ||
    typeof p.access_token !== "string" ||
    p.access_token.length < 32 ||
    typeof p.refresh_token !== "string" ||
    p.refresh_token.length < 32 ||
    !Number.isFinite(p.access_expires_at) ||
    !Number.isFinite(p.refresh_expires_at)
  ) {
    throw new RequestError(
      "invalid_response",
      "The server returned an invalid session",
    );
  }
  return {
    user_id: p.user_id,
    device_id: p.device_id,
    access_token: p.access_token,
    refresh_token: p.refresh_token,
    access_expires_at: p.access_expires_at,
    refresh_expires_at: p.refresh_expires_at,
    installation_id: installation,
  };
}
export function socketUrl(value: string): string {
  const url = new URL(value);
  if (
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/v2/ws" ||
    !(
      url.protocol === "wss:" ||
      (url.protocol === "ws:" &&
        ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname))
    )
  ) {
    throw new Error(
      "Use a secure server URL ending in /v2/ws (localhost can use ws)",
    );
  }
  return url.toString();
}
