import { describe, expect, it } from "vitest";
import { isTyping } from "./useSlashFocus";

describe("isTyping", () => {
  it("reconoce los campos donde se escribe", () => {
    for (const tagName of ["INPUT", "TEXTAREA", "SELECT", "input"]) expect(isTyping({ tagName })).toBe(true);
    expect(isTyping({ tagName: "DIV", isContentEditable: true })).toBe(true);
  });

  it("en el resto de la página las teclas sí son atajos", () => {
    expect(isTyping({ tagName: "BODY" })).toBe(false);
    expect(isTyping({ tagName: "BUTTON" })).toBe(false);
    expect(isTyping({})).toBe(false);
    expect(isTyping(null)).toBe(false);
  });
});
