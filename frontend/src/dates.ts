import { localDate } from "./api";

// Al mediodía para que ninguna zona horaria mueva la fecha de día.
const parse = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`);

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
