import { RefObject, useEffect } from "react";

type MaybeField = { tagName?: string; isContentEditable?: boolean } | null;

/** ¿La persona está escribiendo en un campo? Entonces las teclas sueltas son texto, no atajos. */
export function isTyping(target: MaybeField): boolean {
  if (!target) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes((target.tagName ?? "").toUpperCase()) || !!target.isContentEditable;
}

/** Atajo: pulsar «/» lleva el cursor al campo indicado (como en GitHub o Gmail). */
export default function useSlashFocus(field: RefObject<HTMLElement>) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target as MaybeField)) return;
      e.preventDefault(); // que el «/» no se escriba en el campo recién enfocado
      field.current?.focus();
      field.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [field]);
}
