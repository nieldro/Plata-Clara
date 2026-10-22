import { localDate } from "./api";

// Al mediodía para que ninguna zona horaria mueva la fecha de día.
const parse = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`);

// --- meses (AAAA-MM) ---
const monthStart = (m: string) => new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)) - 1, 1);
const inEs = (m: string, opts: Intl.DateTimeFormatOptions) => monthStart(m).toLocaleDateString("es-CO", opts);

/** «octubre» */
export const monthName = (m: string) => inEs(m, { month: "long" });
/** «oct» */
export const monthShort = (m: string) => inEs(m, { month: "short" });
/** «octubre de 2026» */
export const monthYear = (m: string) => inEs(m, { month: "long", year: "numeric" });
/** «oct 26» */
export const monthShortYear = (m: string) => inEs(m, { month: "short", year: "2-digit" });

/** Mes anterior (−1) o siguiente (+1), cruzando el cambio de año: shiftMonth("2026-01", -1) → "2025-12". */
export function shiftMonth(m: string, delta: number): string {
  const d = new Date(Number(m.slice(0, 4)), Number(m.slice(5, 7)) - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/** «22 oct» a partir de AAAA-MM-DD. */
export const shortDate = (iso: string) =>
  parse(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short" });

/**
 * Fecha pensada para leerse: «Hoy», «Ayer», «Mañana», «22 oct», y con año («22 oct 2025») si es de otro año.
 * `now` solo existe para poder probarla con una fecha fija.
 */
export function friendlyDate(iso: string, now: Date = new Date()): string {
  const day = (offset: number) => localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset));
  if (iso === day(0)) return "Hoy";
  if (iso === day(-1)) return "Ayer";
  if (iso === day(1)) return "Mañana";
  if (Number(iso.slice(0, 4)) === now.getFullYear()) return shortDate(iso);
  return parse(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}
