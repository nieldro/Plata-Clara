const TOKEN_KEY = "token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

export const money = (n: number | string) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(n));

async function send(path: string, init: RequestInit = {}): Promise<Response> {
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
    if (Array.isArray(detail)) {
      // errores de validación de FastAPI: [{msg: "Value error, ..."}]
      throw new Error(detail.map((d) => String(d.msg ?? "").replace(/^Value error, /, "")).join(" · "));
    }
    throw new Error(typeof detail === "string" ? detail : "Error en la solicitud");
  }
  return res;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await send(path, init);
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Lista paginada: el total sin paginar viene en la cabecera X-Total-Count. */
export async function getPage<T>(path: string): Promise<{ items: T[]; total: number }> {
  const res = await send(path);
  const items = (await res.json()) as T[];
  return { items, total: Number(res.headers.get("X-Total-Count") ?? items.length) };
}

/** Descarga un archivo protegido (lleva el token) como Blob, para mostrarlo o abrirlo. */
export async function getBlob(path: string): Promise<Blob> {
  return (await send(path)).blob();
}

export const api = {
  get: <T,>(p: string) => request<T>(p),
  upload: <T,>(p: string, form: FormData) => request<T>(p, { method: "POST", body: form }),
  post: <T,>(p: string, body?: unknown) => request<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) }),
  put: <T,>(p: string, body?: unknown) => request<T>(p, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  patch: <T,>(p: string, body?: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
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
export type AccountType = "savings" | "checking" | "wallet" | "investment" | "credit_card" | "cash";
export const ACCOUNT_TYPES: Record<AccountType, string> = {
  savings: "Cuenta de ahorros",
  checking: "Cuenta corriente",
  wallet: "Billetera digital",
  investment: "Inversión",
  credit_card: "Tarjeta de crédito",
  cash: "Efectivo",
};

export type Institution = { slug: string; name: string; category: string; domain: string; color: string };
export type Account = {
  id: number; name: string; type: AccountType; institution: string | null; institution_name: string | null;
  currency: string; initial_balance: number | string; credit_limit: number | string | null;
  debt_id: number | null; balance: number | string; available: number | string | null;
};

let institutionsCache: Promise<Institution[]> | null = null;
/** Catálogo de entidades (se pide una sola vez). */
export const loadInstitutions = () => (institutionsCache ??= api.get<Institution[]>("/institutions"));
export type Category = { id: number; name: string; kind: "income" | "expense" };
export type Tx = {
  id: number; account_id: number; category_id: number | null;
  kind: "income" | "expense"; amount: number; date: string; note: string; transfer_id?: string | null;
  tags: string[]; attachments: number;
};
export type Attachment = { id: number; filename: string; content_type: string; size: number; created_at: string };
export type TagSummary = { id: number; name: string; count: number; income: number | string; expense: number | string };
export const splitTags = (v: FormDataEntryValue | null) => String(v ?? "").split(",").map((s) => s.trim()).filter(Boolean);
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
