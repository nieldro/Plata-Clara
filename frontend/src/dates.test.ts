import { describe, expect, it } from "vitest";
import { friendlyDate, monthName, monthShort, monthShortYear, monthYear, shiftMonth, shortDate } from "./dates";

describe("meses", () => {
  it("nombran el mes en español", () => {
    expect(monthName("2026-10")).toBe("octubre");
    expect(monthShort("2026-03")).toMatch(/^mar/);
    expect(monthYear("2026-10")).toBe("octubre de 2026");
    expect(monthShortYear("2026-10")).toMatch(/^oct.*26$/);
  });

  it("shiftMonth cruza el cambio de año en los dos sentidos", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2026-10", 0)).toBe("2026-10");
    expect(shiftMonth("2026-10", -13)).toBe("2025-09");
  });
});

const NOW = new Date(2026, 9, 22, 21, 30); // 22 de octubre de 2026, de noche (en UTC ya sería el 23)

describe("friendlyDate", () => {
  it("dice hoy, ayer y mañana", () => {
    expect(friendlyDate("2026-10-22", NOW)).toBe("Hoy");
    expect(friendlyDate("2026-10-21", NOW)).toBe("Ayer");
    expect(friendlyDate("2026-10-23", NOW)).toBe("Mañana");
  });

  it("cruza bien el cambio de mes y de año", () => {
    const primeroDeMes = new Date(2026, 10, 1, 9);
    expect(friendlyDate("2026-10-31", primeroDeMes)).toBe("Ayer");
    const añoNuevo = new Date(2027, 0, 1, 9);
    expect(friendlyDate("2026-12-31", añoNuevo)).toBe("Ayer");
  });

  it("las demás fechas del año van sin año, con el día y el mes abreviado", () => {
    expect(friendlyDate("2026-03-05", NOW)).toMatch(/^5 de mar/i);
    expect(friendlyDate("2026-03-05", NOW)).not.toContain("2026");
  });

  it("las de otro año llevan el año", () => {
    expect(friendlyDate("2025-12-31", NOW)).toContain("2025");
  });
});

describe("shortDate", () => {
  it("da día y mes abreviado", () => {
    expect(shortDate("2026-10-22")).toMatch(/^22 de oct/i);
  });

  it("ignora la hora si la fecha viene con ella", () => {
    expect(shortDate("2026-10-22T03:00:00")).toMatch(/^22 de oct/i);
  });
});
