import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api, money } from "../api";
import { EASE } from "../theme";

type Item = { name: string; key: string; count: number; total: number | string; pct: number };
type Data = { month: string; total_expense: number | string; merchants: number; items: Item[] };

export default function MerchantsCard({ month }: { month: string }) {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => { api.get<Data>(`/insights/merchants?month=${month}&limit=8`).then(setData).catch(() => setData(null)); }, [month]);
  if (!data) return null;

  return (
    <div className="card">
      <h2>Dónde más gastas</h2>
      {data.items.length === 0 ? (
        <p className="empty">Aún no hay gastos este mes. Escribe una nota en cada gasto (Éxito, Rappi, Uber…) y aquí verás a dónde se va tu plata.</p>
      ) : (
        <>
          <p className="empty">Agrupado por la nota de cada gasto: {data.merchants} {data.merchants === 1 ? "comercio" : "comercios"} este mes.</p>
          <ul className="merchants">
            {data.items.map((m) => (
              <li key={m.key || "none"}>
                <div className="m-top">
                  <span>{m.name} <small>· {m.count} {m.count === 1 ? "compra" : "compras"}</small></span>
                  <b>{money(m.total)}</b>
                </div>
                <div className="bar thin">
                  <motion.i initial={{ width: 0 }} whileInView={{ width: `${m.pct}%` }} viewport={{ once: true }} transition={{ duration: 0.9, ease: EASE }} />
                </div>
                <small>{m.pct}% de tus gastos</small>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
