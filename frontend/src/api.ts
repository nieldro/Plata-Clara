const TOKEN_KEY = "token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

export const money = (n: number | string) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(n));

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");

  const res = await fetch(`/api${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    setToken(null);
    location.reload();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    throw new Error(typeof detail === "string" ? detail : "Error en la solicitud");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T,>(p: string) => request<T>(p),
  post: <T,>(p: string, body?: unknown) => request<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) }),
  del: (p: string) => request<void>(p, { method: "DELETE" }),
  login: async (email: string, password: string) => {
    const r = await request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    });
    setToken(r.access_token);
  },
};

// --- tipos ---
export type Account = { id: number; name: string; type: string; balance: number; currency: string };
export type Category = { id: number; name: string; kind: "income" | "expense" };
export type Tx = {
  id: number; account_id: number; category_id: number | null;
  kind: "income" | "expense"; amount: number; date: string; note: string;
};
export type Debt = {
  id: number; name: string; kind: "credit_card" | "loan"; original_amount: number;
  current_balance: number; rate: number; rate_type: "EA" | "MV" | "NA";
  term_months: number | null; monthly_payment: number | null;
};
export type Row = { n: number; payment: number; interest: number; principal: number; balance: number };
export type Plan = {
  monthly_rate_pct?: number; payment?: number; months: number; total_interest: number;
  total_paid: number; months_saved?: number; interest_saved?: number; rows: Row[];
};
export type Goal = {
  id: number; name: string; target_amount: number; current_amount: number;
  target_date: string; annual_rate: number;
};
