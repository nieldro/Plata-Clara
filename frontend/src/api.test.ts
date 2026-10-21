import { afterEach, describe, expect, it } from "vitest";
import { isPrivate, localDate, localMonth, money, setPrivate, splitTags } from "./api";

describe("localDate / localMonth", () => {
  it("usan la fecha local, no la de UTC (el error que adelantaba el día por la noche en Colombia)", () => {
    // 22:30 del 15 de octubre en la hora LOCAL de esta máquina; en UTC puede ser ya el 16.
    const noche = new Date(2026, 9, 15, 22, 30);
    expect(localDate(noche)).toBe("2026-10-15");
    expect(localMonth(noche)).toBe("2026-10");
  });

  it("el último día del mes por la noche sigue siendo ese mes", () => {
    expect(localMonth(new Date(2026, 9, 31, 23, 59))).toBe("2026-10");
    expect(localMonth(new Date(2026, 10, 1, 0, 1))).toBe("2026-11");
  });

  it("rellena con ceros el mes y el día", () => {
    expect(localDate(new Date(2026, 0, 5, 12))).toBe("2026-01-05");
    expect(localDate(new Date(2026, 11, 31, 12))).toBe("2026-12-31");
  });

  it("sin argumentos devuelve el día de hoy con formato AAAA-MM-DD", () => {
    expect(localDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(localMonth()).toMatch(/^\d{4}-\d{2}$/);
    expect(localDate().startsWith(localMonth())).toBe(true);
  });
});

describe("splitTags", () => {
  it("separa por comas, recorta y descarta vacíos", () => {
    expect(splitTags("viaje, comida ,, regalo ")).toEqual(["viaje", "comida", "regalo"]);
  });

  it("tolera valores ausentes", () => {
    expect(splitTags(null)).toEqual([]);
    expect(splitTags("")).toEqual([]);
    expect(splitTags("   ")).toEqual([]);
  });
});

describe("modo privacidad", () => {
  afterEach(() => setPrivate(false)); // que una prueba no deje el modo activado para las demás

  it("oculta cualquier monto, sin dejar ver ni un dígito", () => {
    setPrivate(true);
    expect(isPrivate()).toBe(true);
    for (const value of [0, 1234567, "50000", -999, 0.5]) {
      const text = money(value);
      expect(text).toContain("•");
      expect(text).not.toMatch(/\d/);
    }
  });

  it("al desactivarlo vuelve a mostrar los montos", () => {
    setPrivate(true);
    setPrivate(false);
    expect(isPrivate()).toBe(false);
    expect(money(1234567).replace(/\s| /g, "")).toBe("$1.234.567");
  });

  it("funciona aunque el navegador no permita guardar la preferencia", () => {
    // en este entorno de pruebas no existe localStorage: no debe lanzar errores
    expect(() => setPrivate(true)).not.toThrow();
    expect(isPrivate()).toBe(true);
  });
});

describe("money", () => {
  const plain = (s: string) => s.replace(/\s| /g, "");

  it("da formato de pesos sin decimales", () => {
    expect(plain(money(1234567))).toBe("$1.234.567");
    expect(plain(money("50000"))).toBe("$50.000");
    expect(plain(money(0))).toBe("$0");
  });

  it("redondea los centavos y respeta los negativos", () => {
    expect(plain(money(1999.6))).toBe("$2.000");
    expect(plain(money(-50000))).toContain("50.000");
    expect(plain(money(-50000))).toContain("-");
  });
});
