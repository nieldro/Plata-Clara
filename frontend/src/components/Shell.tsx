import { AnimatePresence, motion } from "framer-motion";
import { ReactNode, useEffect, useState } from "react";
import { api } from "../api";
import Budgets from "../pages/Budgets";
import Dashboard from "../pages/Dashboard";
import Debts from "../pages/Debts";
import Savings from "../pages/Savings";
import Simulator from "../pages/Simulator";
import Transactions from "../pages/Transactions";
import { EASE } from "../theme";
import { Icons, Logo } from "./Icons";
import NotificationBell from "./NotificationBell";

const TABS: { key: string; label: string; icon: ReactNode; page: () => JSX.Element }[] = [
  { key: "home", label: "Resumen", icon: Icons.home, page: Dashboard },
  { key: "tx", label: "Cuentas y movimientos", icon: Icons.swap, page: Transactions },
  { key: "budgets", label: "Presupuestos", icon: Icons.pie, page: Budgets },
  { key: "debts", label: "Deudas y tarjetas", icon: Icons.card, page: Debts },
  { key: "savings", label: "Ahorro", icon: Icons.target, page: Savings },
  { key: "sim", label: "Simulador", icon: Icons.calc, page: Simulator },
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
          {ready && <NotificationBell />}
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
            {ready && <Page />}
          </motion.div>
        </AnimatePresence>
      </section>
    </div>
  );
}
