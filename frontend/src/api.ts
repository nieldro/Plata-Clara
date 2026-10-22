import { messageFor, NETWORK_ERROR, TIMEOUT_ERROR } from "./errors";

const TOKEN_KEY = "token";
const REQUEST_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 120_000;

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

/** Fecha de hoy (AAAA-MM-DD) en la hora del usuario. `toISOString()` da la de UTC: después de las 7 p. m. en Colombia ya sería mañana. */
export const localDate = (d: Date = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Mes actual (AAAA-MM) en la hora del usuario. */
export const localMonth = (d: Date = new Date()) => localDate(d).slice(0, 7);

// Modo privacidad: oculta todos los montos de la pantalla (por si alguien mira por encima del hombro).
const PRIVACY_KEY = "privacy";
const HIDDEN = "$ ••••••";
let hideAmounts = (() => {
  try { return localStorage.getItem(PRIVACY_KEY) === "1"; } catch { return false; }
})();

export const isPrivate = () => hideAmounts;
export function setPrivate(value: boolean) {
  hideAmounts = value;
  try { value ? localStorage.setItem(PRIVACY_KEY, "1") : localStorage.removeItem(PRIVACY_KEY); } catch { /* sin almacenamiento: dura mientras la página siga abierta */ }
}

export const money = (n: number | string) =>
  hideAmounts ? HIDDEN : new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(Number(n));

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");

  // Sin tope, una conexión colgada deja la pantalla cargando para siempre. Subir un extracto es más lento que lo demás.
  const controller = new AbortController();
  const limit = init.body instanceof FormData ? UPLOAD_TIMEOUT_MS : REQUEST_TIMEOUT_MS;
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, limit);

  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers, signal: controller.signal });
  } catch {
    throw new Error(timedOut ? TIMEOUT_ERROR : NETWORK_ERROR); // servidor apagado, sin internet o bloqueado
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 401 && token) {
    setToken(null);
    location.reload();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(messageFor(res.status, body));
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

/** Si ya hay un movimiento casi idéntico (misma cuenta, tipo y monto, ±2 días), pregunta si de verdad se quiere guardar otro. */
export async function confirmIfDuplicate(m: { account_id: number; amount: number; date: string; kind: "income" | "expense" }): Promise<boolean> {
  try {
    const found = await request<{ date: string; note: string; amount: number | string }[]>(
      `/transactions/similar?account_id=${m.account_id}&amount=${m.amount}&date=${m.date}&kind=${m.kind}`);
    if (found.length === 0) return true;
    const first = found[0];
    const what = first.note ? `«${first.note}»` : "un movimiento";
    return confirm(
      `Ya registraste ${what} por ${money(first.amount)} el ${first.date}` +
      `${found.length > 1 ? ` (y ${found.length - 1} más parecido${found.length > 2 ? "s" : ""})` : ""}.\n\n¿Guardar este de todos modos?`);
  } catch {
    return true; // si no se pudo comprobar, no se estorba: es solo un aviso
  }
}

/** Descarga un archivo protegido (lleva el token) como Blob, para mostrarlo o abrirlo. */
export async function getBlob(path: string): Promise<Blob> {
  return (await send(path)).blob();
}

/** Descarga un archivo del servidor y lo guarda en el computador con el nombre que indique la API. */
export async function download(path: string, fallbackName = "descarga"): Promise<void> {
  const res = await send(path);
  const blob = await res.blob();
  const name = /filename="?([^";]+)"?/i.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
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
  tags: string[]; attachments: number; loan_id?: number | null;
};
export type Attachment = { id: number; filename: string; content_type: string; size: number; created_at: string };
export type TagSummary = { id: number; name: string; count: number; income: number | string; expense: number | string };
export const splitTags = (v: FormDataEntryValue | null) => String(v ?? "").split(",").map((s) => s.trim()).filter(Boolean);
export type Debt = {
  id: number; name: string; kind: "credit_card" | "loan"; original_amount: number;
  current_balance: number; rate: number; rate_type: "EA" | "MV" | "NA";
  term_months: number | null; monthly_payment: number | null; due_day: number | null;
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
