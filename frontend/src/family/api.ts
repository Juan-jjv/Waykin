// Client for /api/me (accounts and families). The session cookie is scoped to /api/me by the server, so it is
// never sent with route requests.
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import type {
  AccountOut, FamilyDetail, FamilySummary, InviteCreated, InvitePreview, JourneyCreated,
} from "../api/types";

async function me<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/me${path}`, {
      credentials: "same-origin",
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the WayKin server");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body?.error?.code ?? "validation", body?.error?.message ?? `HTTP ${res.status}`);
  return body as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const accountApi = {
  /** The signed-in account, or null. */
  account: () => me<AccountOut>("/account").catch((e) => {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }),
  signUp: (display_name: string, login: string, password: string) =>
    me<AccountOut>("/account", post({ display_name, login, password })),
  logIn: (login: string, password: string) => me<AccountOut>("/session", post({ login, password })),
  logOut: () => me<void>("/session", { method: "DELETE" }),
  deleteAccount: () => me<void>("/account", { method: "DELETE" }),
  setPublicKey: (public_key: string) => me<void>("/account/public-key", { method: "PUT", body: JSON.stringify({ public_key }) }),
  families: () => me<FamilySummary[]>("/families"),
  createFamily: (name: string, wrapped_key: string) => me<FamilyDetail>("/families", post({ name, wrapped_key })),
  family: (fid: string) => me<FamilyDetail>(`/families/${encodeURIComponent(fid)}`),
  createInvite: (fid: string) => me<InviteCreated>(`/families/${encodeURIComponent(fid)}/invites`, { method: "POST" }),
  invitePreview: (fid: string, invite_token: string) =>
    me<InvitePreview>(`/families/${encodeURIComponent(fid)}/invite-preview`, post({ invite_token })),
  join: (fid: string, invite_token: string, wrapped_key: string, key_version: number) =>
    me<FamilyDetail>(`/families/${encodeURIComponent(fid)}/join`, post({ invite_token, wrapped_key, key_version })),
  removeMember: (fid: string, aid: string) =>
    me<void>(`/families/${encodeURIComponent(fid)}/members/${encodeURIComponent(aid)}`, { method: "DELETE" }),
  rotateKeys: (fid: string, key_version: number, wrapped: Record<string, string>) =>
    me<void>(`/families/${encodeURIComponent(fid)}/keys`, { method: "PUT", body: JSON.stringify({ key_version, wrapped }) }),
  startFamilyJourney: (fid: string, wrapped_journey_key: string, key_version: number, expires_in_min = 120) =>
    me<JourneyCreated>(`/families/${encodeURIComponent(fid)}/journeys`,
      post({ wrapped_journey_key, key_version, expires_in_min })),
};

export const useAccount = () => useQuery({ queryKey: ["account"], queryFn: accountApi.account, staleTime: 60_000, retry: false });

export const useFamilies = (enabled: boolean) =>
  useQuery({ queryKey: ["families"], queryFn: accountApi.families, enabled, retry: false });

export const useFamily = (fid: string | null) =>
  useQuery({ queryKey: ["family", fid], queryFn: () => accountApi.family(fid!), enabled: Boolean(fid), retry: false });

/** Opens the family stream (journey and membership events). Reconnects with backoff while mounted. */
export function openFamilyStream(onEvent: (e: { type: string; [k: string]: unknown }) => void): () => void {
  let ws: WebSocket | null = null;
  let stopped = false;
  let backoff = 1000;
  const connect = () => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/api/me/stream`);
    ws.onmessage = (ev) => {
      backoff = 1000;
      try {
        onEvent(JSON.parse(ev.data as string));
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = (ev) => {
      if (stopped || ev.code === 4401) return;
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 15_000);
    };
  };
  connect();
  return () => {
    stopped = true;
    ws?.close();
  };
}
