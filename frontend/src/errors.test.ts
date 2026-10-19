import { describe, expect, it } from "vitest";
import { messageFor, NETWORK_ERROR } from "./errors";

describe("messageFor", () => {
  it("usa el mensaje de la API cuando viene como texto", () => {
    expect(messageFor(409, { detail: "Ese correo ya está registrado" })).toBe("Ese correo ya está registrado");
  });

  it("une los errores de validación y quita el prefijo técnico", () => {
    const body = { detail: [{ msg: "Value error, Elige una entidad" }, { msg: "Monto inválido" }] };
    expect(messageFor(422, body)).toBe("Elige una entidad · Monto inválido");
  });

  it("si la validación no trae texto útil, cae al mensaje por código", () => {
    expect(messageFor(422, { detail: [{ msg: "" }, {}] })).toBe("No se pudo completar la solicitud.");
  });

  it("explica los errores de servidor aunque no haya cuerpo JSON (p. ej. página de error de nginx)", () => {
    expect(messageFor(502, null)).toContain("no está disponible");
    expect(messageFor(503, null)).toContain("no está disponible");
    expect(messageFor(504, undefined)).toContain("no está disponible");
    expect(messageFor(500, null)).toContain("error inesperado");
    expect(messageFor(500, { detail: { status: "error" } })).toContain("error inesperado"); // detail no es texto
  });

  it("mensajes para otros códigos frecuentes", () => {
    expect(messageFor(413, null)).toContain("demasiado grande");
    expect(messageFor(429, null)).toContain("Demasiados intentos");
    expect(messageFor(404, null)).toContain("No se encontró");
    expect(messageFor(418, null)).toBe("No se pudo completar la solicitud.");
  });

  it("ignora un cuerpo que no es un objeto", () => {
    expect(messageFor(500, "texto suelto")).toContain("error inesperado");
    expect(messageFor(400, 42)).toBe("No se pudo completar la solicitud.");
  });

  it("el error de red habla de conexión", () => {
    expect(NETWORK_ERROR).toContain("conectar");
  });
});
