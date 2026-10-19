import { useEffect } from "react";

/** Llama a `onEscape` cuando se pulsa la tecla Esc (para cerrar ventanas emergentes). */
export default function useEscape(onEscape: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onEscape();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onEscape]);
}
