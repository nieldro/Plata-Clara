import { motion } from "framer-motion";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, Category, localMonth, money } from "../api";
import RecurringSection from "../components/RecurringSection";
import { EASE } from "../theme";

type Item = { category_id: number; category: string; amount: number; spent: number; remaining: number; pct: number };

const shift = (month: string, delta: number) => {
  const d = new Date(Number(month.slice(0, 4)), Number(month.slice(5)) - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};
const label = (month: string) =>
  new Date(Number(month.slice(0, 4)), Number(month.slice(5)) - 1).toLocaleDateString("es-CO", { month: "long", year: "numeric" });

export const levelOf = (pct: number) => (pct > 100 ? "over" : pct >= 80 ? "warn" : "ok");

export default function Budgets() {
  const [month, setMonth] = useState(localMonth());
  const [items, setItems] = useState<Item[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const r = await api.get<{ items: Item[] }>(`/budgets?month=${month}`);
    setItems(r.items);
  }, [month]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get<Category[]>("/categories").then(setCats); }, []);

  const free = cats.filter((c) => c.kind === "expense" && !items.some((i) => i.category_id === c.id));
  const totalLimit = items.reduce((a, i) => a + Number(i.amount), 0);
  const totalSpent = items.reduce((a, i) => a + Number(i.spent), 0);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.put(`/budgets/${f.get("category")}`, { amount: Number(f.get("amount")) });
      form.reset();
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function edit(i: Item) {
    const v = Number(prompt(`Nuevo tope mensual para ${i.category}`, String(Number(i.amount))));
    if (v > 0) {
      await api.put(`/budgets/${i.category_id}`, { amount: v });
      load();
    }
  }

  return (
    <>
      <div className="card">
        <div className="month-nav">
          <button className="link" onClick={() => setMonth(shift(month, -1))}>←</button>
          <h2>{label(month)}</h2>
          <button className="link" onClick={() => setMonth(shift(month, 1))}>→</button>
        </div>
        {items.length > 0 && (
          <p className="empty">
            Llevas <b>{money(totalSpent)}</b> de <b>{money(totalLimit)}</b> presupuestados ({Math.round((totalSpent / totalLimit) * 100)}%).
          </p>
        )}
        <form className="row" onSubmit={add}>
          <select name="category" required>
            <option value="">Categoría de gasto…</option>
            {free.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input name="amount" type="number" min="1" step="1" placeholder="Tope mensual" required />
          <button>Crear presupuesto</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {items.length === 0 && <p className="empty">Aún no tienes presupuestos. Crea uno para controlar lo que gastas en cada categoría.</p>}

      <div className="budget-grid">
        {items.map((i) => (
          <div className="card budget" key={i.category_id}>
            <div className="budget-head">
              <h2>{i.category}</h2>
              <span className={`pill ${levelOf(i.pct)}`}>{i.pct}%</span>
            </div>
            <div className="bar">
              <motion.i
                className={levelOf(i.pct)}
                initial={{ width: 0 }}
                whileInView={{ width: `${Math.min(i.pct, 100)}%` }}
                viewport={{ once: true }}
                transition={{ duration: 1.1, ease: EASE }}
              />
            </div>
            <p className="budget-nums">
              <span>Gastado <b>{money(i.spent)}</b></span>
              <span className={Number(i.remaining) < 0 ? "neg" : "pos"}>
                {Number(i.remaining) < 0 ? `Excedido ${money(-Number(i.remaining))}` : `Quedan ${money(i.remaining)}`}
              </span>
            </p>
            <small>Tope {money(i.amount)}</small>{" "}
            <button className="link" onClick={() => edit(i)}>Editar</button>
            <button className="link" onClick={() => api.del(`/budgets/${i.category_id}`).then(load)}>Quitar</button>
          </div>
        ))}
      </div>

      <RecurringSection />
    </>
  );
}
