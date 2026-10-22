import { AnimatePresence, motion } from "framer-motion";
import { ComponentType, lazy, ReactNode, Suspense, useEffect, useState } from "react";
import { api, isPrivate, setPrivate } from "../api";
import { EASE } from "../theme";
import ErrorBoundary from "./ErrorBoundary";
import { Icons, Logo } from "./Icons";
import NotificationBell from "./NotificationBell";
import PageLoading from "./PageLoading";

// Cada pantalla se descarga solo cuando entras a ella (así la primera carga es mucho más liviana).
const Dashboard = lazy(() => import("../pages/Dashboard"));
const Transactions = lazy(() => import("../pages/Transactions"));
const Annual = lazy(() => import("../pages/Annual"));
const Import = lazy(() => import("../pages/Import"));
const Loans = lazy(() => import("../pages/Loans"));
const Budgets = lazy(() => import("../pages/Budgets"));
const Debts = lazy(() => import("../pages/Debts"));
const Savings = lazy(() => import("../pages/Savings"));
const Assistant = lazy(() => import("../pages/Assistant"));
const Simulator = lazy(() => import("../pages/Simulator"));
const Settings = lazy(() => import("../pages/Settings"));

const TABS: { key: string; label: string; icon: ReactNode; page: ComponentType }[] = [
  { key: "home", label: "Resumen", icon: Icons.home, page: Dashboard },
  { key: "tx", label: "Cuentas y movimientos", icon: Icons.swap, page: Transactions },
  { key: "annual", label: "Mi año", icon: Icons.calendar, page: Annual },
  { key: "import", label: "Importar extracto", icon: Icons.upload, page: Import },
  { key: "loans", label: "Quién me debe", icon: Icons.users, page: Loans },
  { key: "budgets", label: "Presupuestos", icon: Icons.pie, page: Budgets },
  { key: "debts", label: "Deudas y tarjetas", icon: Icons.card, page: Debts },
  { key: "savings", label: "Ahorro", icon: Icons.target, page: Savings },
  { key: "assistant", label: "Asistente", icon: Icons.spark, page: Assistant },
  { key: "sim", label: "Simulador", icon: Icons.calc, page: Simulator },
  { key: "settings", label: "Ajustes", icon: Icons.gear, page: Settings },
];

export default function Shell({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState(TABS[0].key);
  const [name, setName] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    api.get<{ name: string }>("/auth/me").then((u) => setName(u.name)).catch(() => {});
    // Registra los recurrentes vencidos antes de pintar los datos.
    api.post("/recurring/run").catch(() => {}).finally(() => setReady(true));
  }, []);

  const current = TABS.find((t) => t.key === tab)!;
  const Page = current.page;

  // Modo privacidad: al cambiarlo se vuelve a dibujar la pantalla para que todos los montos se actualicen.
  const [priv, setPriv] = useState(isPrivate());
  const togglePrivacy = () => { setPrivate(!priv); setPriv(!priv); };

  // El título de la pestaña del navegador dice en qué sección estás; al salir se restaura el original.
  useEffect(() => {
    const original = document.title;
    document.title = `${current.label} · Plata Clara`;
    return () => { document.title = original; };
  }, [current.label]);

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><Logo /> <span>Plata Clara</span></div>
        <nav>
          {TABS.map((t) => (
            <button key={t.key} className={`nav-item ${t.key === tab ? "active" : ""}`} onClick={() => { setTab(t.key); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
              {t.key === tab && <motion.span layoutId="nav-pill" className="nav-pill" transition={{ duration: 0.5, ease: EASE }} />}
              <span className="nav-icon">{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </nav>
        <button className="nav-item logout" onClick={onLogout}>
          <span className="nav-icon">{Icons.logout}</span><span>Salir</span>
        </button>
      </aside>

      <section className="content">
        <header className="page-head">
          <div>
            <small>{name ? `Hola, ${name}` : " "}</small>
            <h1>{current.label}</h1>
          </div>
          <div className="head-tools">
            <button className="bell" onClick={togglePrivacy} aria-pressed={priv}
              aria-label={priv ? "Mostrar los montos" : "Ocultar los montos"} title={priv ? "Mostrar los montos" : "Ocultar los montos"}>
              {priv ? Icons.eyeOff : Icons.eye}
            </button>
            {ready && <NotificationBell />}
          </div>
        </header>
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            className="page"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.45, ease: EASE }}
          >
            {ready && (
              <ErrorBoundary resetKey={tab}>
                <Suspense fallback={<PageLoading />}><Page key={String(priv)} /></Suspense>
              </ErrorBoundary>
            )}
          </motion.div>
        </AnimatePresence>
      </section>
    </div>
  );
}
