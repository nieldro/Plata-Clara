import { motion } from "framer-motion";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { api, Goal, money } from "../api";
import { EASE, GOLD, MUTED, tooltipStyle } from "../theme";

type PlanInfo = {
  months_left: number; monthly_contribution: number; missing: number; progress_pct: number;
  projection: { month: number; label: string; balance: number }[];
};
type Contribution = { id: number; amount: number; date: string; note: string };

export default function Savings() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [plans, setPlans] = useState<Record<number, PlanInfo>>({});
  const [open, setOpen] = useState<number | null>(null);
  const [history, setHistory] = useState<Contribution[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const gs = await api.get<Goal[]>("/savings");
    setGoals(gs);
    const entries = await Promise.all(gs.map(async (g) => [g.id, await api.get<PlanInfo>(`/savings/${g.id}/plan`)] as const));
    setPlans(Object.fromEntries(entries));
  }, []);
  useEffect(() => { load(); }, [load]);

  const loadHistory = async (id: number) => setHistory(await api.get(`/savings/${id}/contributions`));
  async function toggle(id: number) {
    if (open === id) return setOpen(null);
    setOpen(id);
    loadHistory(id);
  }

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/savings", {
        name: f.get("name"), target_amount: Number(f.get("target")),
        current_amount: Number(f.get("current") || 0), target_date: f.get("date"),
        annual_rate: Number(f.get("rate") || 0),
      });
      form.reset();
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function move(id: number, kind: "deposit" | "withdraw") {
    const amount = Number(prompt(kind === "deposit" ? "¿Cuánto aportas?" : "¿Cuánto retiras de la meta?"));
    if (!(amount > 0)) return;
    const note = prompt("Nota (opcional)") ?? "";
    try {
      await api.post(`/savings/${id}/contributions`, { amount, kind, note });
      setError("");
      await load();
      if (open === id) loadHistory(id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function edit(g: Goal) {
    const name = prompt("Nombre de la meta", g.name);
    if (name === null) return;
    const target = prompt("Monto objetivo", String(Number(g.target_amount)));
    if (target === null) return;
    const date = prompt("Fecha objetivo (AAAA-MM-DD)", g.target_date);
    if (date === null) return;
    const rate = prompt("Rendimiento % EA", String(Number(g.annual_rate)));
    if (rate === null) return;
    try {
      await api.patch(`/savings/${g.id}`, {
        name: name.trim() || undefined, target_amount: Number(target) || undefined,
        target_date: date || undefined, annual_rate: Number(rate) >= 0 ? Number(rate) : undefined,
      });
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeContribution(goalId: number, cid: number) {
    await api.del(`/savings/${goalId}/contributions/${cid}`);
    await load();
    loadHistory(goalId);
  }

  return (
    <>
      <div className="card">
        <h2>Nueva meta de ahorro</h2>
        <form className="row" onSubmit={add}>
          <input name="name" placeholder="Meta (ej. Viaje, Fondo de emergencia)" required />
          <input name="target" type="number" step="0.01" min="1" placeholder="Monto objetivo" required />
          <input name="current" type="number" step="0.01" min="0" placeholder="Ya tengo" />
          <input name="date" type="date" required title="Fecha objetivo" />
          <input name="rate" type="number" step="0.01" min="0" placeholder="Rinde % EA (opcional)" />
          <button>Crear</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {goals.length === 0 && <p className="empty">Aún no tienes metas. Crea una y te digo cuánto ahorrar cada mes.</p>}

      {goals.map((g) => {
        const p = plans[g.id];
        const done = Number(g.current_amount) >= Number(g.target_amount);
        return (
          <div className="card" key={g.id}>
            <div className="budget-head">
              <h2>{g.name}</h2>
              <span className={`pill ${done ? "" : "warn"}`}>{done ? "¡Lograda!" : `${p?.progress_pct ?? 0}%`}</span>
            </div>
            <div className="bar">
              <motion.i initial={{ width: 0 }} animate={{ width: `${Math.min(p?.progress_pct ?? 0, 100)}%` }} transition={{ duration: 1.1, ease: EASE }} />
            </div>
            <p>
              {money(g.current_amount)} de {money(g.target_amount)} · meta {g.target_date}
              {Number(g.annual_rate) > 0 && <> · rinde {Number(g.annual_rate)}% EA</>}
            </p>
            {p && !done && (
              <p>
                Para llegar en {p.months_left} {p.months_left === 1 ? "mes" : "meses"} debes ahorrar{" "}
                <b className="pos">{money(p.monthly_contribution)}</b> al mes.
              </p>
            )}
            <div className="row">
              <button onClick={() => move(g.id, "deposit")}>Aportar</button>
              <button className="btn-ghost" onClick={() => move(g.id, "withdraw")}>Retirar</button>
              <button className="link" onClick={() => edit(g)}>Editar</button>
              <button className="link" onClick={() => toggle(g.id)}>{open === g.id ? "Ocultar detalle" : "Ver detalle"}</button>
              <button className="link" onClick={() => confirm(`¿Eliminar la meta «${g.name}»?`) && api.del(`/savings/${g.id}`).then(load)}>Eliminar</button>
            </div>

            {open === g.id && p && (
              <>
                {!done && (
                  <>
                    <small>Proyección con el aporte sugerido</small>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={p.projection} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                          <defs>
                            <linearGradient id={`sv${g.id}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0" stopColor={GOLD} stopOpacity={0.4} /><stop offset="1" stopColor={GOLD} stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <XAxis dataKey="label" stroke={MUTED} tickLine={false} axisLine={false} fontSize={11} minTickGap={30} />
                          <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} />
                          <Area name="Ahorro" dataKey="balance" stroke={GOLD} strokeWidth={2} fill={`url(#sv${g.id})`} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </>
                )}
                <small>Historial</small>
                <table>
                  <tbody>
                    {history.map((c) => (
                      <tr key={c.id}>
                        <td>{c.date}</td><td>{c.note}</td>
                        <td className={`num ${Number(c.amount) >= 0 ? "pos" : "neg"}`}>{Number(c.amount) >= 0 ? "+" : "−"}{money(Math.abs(Number(c.amount)))}</td>
                        <td><button className="link" onClick={() => removeContribution(g.id, c.id)}>✕</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {history.length === 0 && <p className="empty">Sin aportes todavía.</p>}
              </>
            )}
          </div>
        );
      })}
    </>
  );
}
