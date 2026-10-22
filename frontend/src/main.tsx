import "@fontsource-variable/inter";
import "@fontsource/cormorant-garamond/500.css";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource/cormorant-garamond/500-italic.css";
import { MotionConfig } from "framer-motion";
import Lenis from "lenis";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./styles.css";

// Scroll suave (Lenis). Se desactiva si el usuario pidió menos movimiento.
if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const lenis = new Lenis({ lerp: 0.09, wheelMultiplier: 0.9 });
  const raf = (t: number) => {
    lenis.raf(t);
    requestAnimationFrame(raf);
  };
  requestAnimationFrame(raf);
}

// App instalable y con carcasa sin conexión. Solo en producción: en desarrollo un service worker estorba (cachea).
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => { /* sin service worker la app funciona igual */ });
  });
}

// Brillo que sigue al cursor dentro de las tarjetas.
document.addEventListener("pointermove", (e) => {
  const card = (e.target as HTMLElement).closest?.<HTMLElement>(".card");
  if (!card) return;
  const r = card.getBoundingClientRect();
  card.style.setProperty("--mx", `${e.clientX - r.left}px`);
  card.style.setProperty("--my", `${e.clientY - r.top}px`);
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* reducedMotion="user": con «reducir movimiento» activo en el sistema, las animaciones de desplazamiento se omiten */}
    <MotionConfig reducedMotion="user">
      <ErrorBoundary scope="app">
        <App />
      </ErrorBoundary>
    </MotionConfig>
  </StrictMode>,
);
