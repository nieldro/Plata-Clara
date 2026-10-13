import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, Goal, money } from "../api";

type PlanInfo = { months_left: number; monthly_contribution: number; missing: number; progress_pct: number };

export default function Savings() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [plans, setPlans] = useState<Record<number, PlanInfo>>({});

  const load = useCallback(async () => {
    const gs = await api.get<Goal[]>("/savings");
    setGoals(gs);
    const entries = await Promise.all(gs.map(async (g) => [g.id, await api.get<PlanInfo>(`/savings/${g.id}/plan`)] as const));
    setPlans(Object.fromEntries(entries));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    await api.post("/savings", {
      name: f.get("name"), target_amount: Number(f.get("target")),
      current_amount: Number(f.get("current") || 0), target_date: f.get("date"),
      annual_rate: Number(f.get("rate") || 0),
    });
    form.reset();
    load();
  }

  async function contribute(id: number) {
    const amount = Number(prompt("¿Cuánto aportas?"));
    if (amount > 0) {
      await api.post(`/savings/${id}/contributions`, { amount });
      load();
    }
  }

  return (
    <>
      <div className="card">
        <h2>Nueva meta de ahorro</h2>
        <form className="row" onSubmit={add}>
          <input name="name" placeholder="Meta (ej. Viaje, Fondo de emergencia)" required />
          <input name="target" type="number" step="0.01" placeholder="Monto objetivo" required />
          <input name="current" type="number" step="0.01" placeholder="Ya tengo" />
          <input name="date" type="date" required />
          <input name="rate" type="number" step="0.01" placeholder="Rinde % EA (opcional)" />
          <button>Crear</button>
        </form>
      </div>
      {goals.map((g) => {
        const p = plans[g.id];
        return (
          <div className="card" key={g.id}>
            <h2>{g.name}</h2>
            <progress value={p?.progress_pct ?? 0} max={100} />
            <p>
              {money(g.current_amount)} de {money(g.target_amount)} ({p?.progress_pct}%) · meta {g.target_date}
            </p>
            {p && (
              <p>
                Para llegar en {p.months_left} meses debes ahorrar{" "}
                <b className="pos">{money(p.monthly_contribution)}</b> al mes.
              </p>
            )}
            <button onClick={() => contribute(g.id)}>Aportar</button>{" "}
            <button className="link" onClick={() => api.del(`/savings/${g.id}`).then(load)}>Eliminar</button>
          </div>
        );
      })}
    </>
  );
}
