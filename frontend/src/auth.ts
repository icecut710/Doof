// DOOF client session helpers — remember-me across launches (localStorage)
// or per-run (sessionStorage).

export type Profile = {
  id: string;
  email: string;
  name: string;
  role: "owner" | "trusted" | "viewer";
  provider?: string;
};

const TOKEN_KEY = "doof_token";
export const SERVER_KEY = "doof_server";

export function getServer(): string {
  return localStorage.getItem(SERVER_KEY) || "http://127.0.0.1:8765";
}

export function setServer(url: string) {
  if (url.trim()) localStorage.setItem(SERVER_KEY, url.trim().replace(/\/$/, ""));
  else localStorage.removeItem(SERVER_KEY);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string, remember: boolean) {
  if (remember) localStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}
