import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, Debt, localDate, money, Plan } from "../api";
import ScheduleTable from "../components/ScheduleTable";

export default function Debts() {
  const [debts, setDebts] = useState<Debt[]>([]);
  const [plan, setPlan] = useState<{ id: number; data: Plan } | null>(null);
  const [extra, setExtra] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(async () => setDebts(await api.get("/debts")), []);
  useEffect(() => { load(); }, [load]);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const num = (k: string) => (f.get(k) ? Number(f.get(k)) : null);
    try {
      await api.post("/debts", {
        name: f.get("name"), kind: f.get("kind"),
        original_amount: num("balance"), current_balance: num("balance"),
        rate: num("rate"), rate_type: f.get("rate_type"),
        term_months: num("term"), monthly_payment: num("payment"),
      });
      form.reset();
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function project(id: number, ex = extra) {
    try {
      setPlan({ id, data: await api.get<Plan>(`/debts/${id}/schedule?extra=${ex}`) });
      setError("");
    } catch (err) {
      setPlan(null);
      setError((err as Error).message);
    }
  }

  async function pay(id: number) {
    const amount = Number(prompt("¿Cuánto pagaste?"));
    if (!amount) return;
    await api.post(`/debts/${id}/payments`, { amount, date: localDate() });
    load();
  }

  return (
    <>
      <div className="card">
        <h2>Nueva tarjeta o crédito</h2>
        <form className="row" onSubmit={add}>
          <input name="name" placeholder="Nombre (ej. Visa Davivienda)" required />
          <select name="kind"><option value="credit_card">Tarjeta de crédito</option><option value="loan">Crédito</option></select>
          <input name="balance" type="number" step="0.01" placeholder="Saldo actual" required />
          <input name="rate" type="number" step="0.01" placeholder="Tasa %" required />
          <select name="rate_type">
            <option value="EA">Efectiva anual</option>
            <option value="MV">Mensual vencida</option>
            <option value="NA">Nominal anual</option>
          </select>
          <input name="term" type="number" placeholder="Plazo (meses)" />
          <input name="payment" type="number" step="0.01" placeholder="Cuota/pago mensual" />
          <button>Agregar</button>
        </form>
        <small>Crédito: pon el plazo y calculo la cuota. Tarjeta: pon cuánto pagas al mes.</small>
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <h2>Mis deudas</h2>
        <table>
          <thead><tr><th>Nombre</th><th>Tipo</th><th>Tasa</th><th className="num">Saldo</th><th /></tr></thead>
          <tbody>
            {debts.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td>{d.kind === "credit_card" ? "Tarjeta" : "Crédito"}</td>
                <td>{d.rate}% {d.rate_type}</td>
                <td className="num neg">{money(d.current_balance)}</td>
                <td>
                  <button onClick={() => project(d.id)}>Proyectar</button>{" "}
                  <button onClick={() => pay(d.id)}>Registrar pago</button>{" "}
                  <button className="link" aria-label={`Eliminar ${d.name}`} onClick={() => api.del(`/debts/${d.id}`).then(load)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {plan && (
        <div className="card">
          <h2>Proyección</h2>
          <div className="row">
            <label>¿Y si abono extra cada mes?
              <input type="number" min="0" value={extra} onChange={(e) => setExtra(Number(e.target.value))} />
            </label>
            <button onClick={() => project(plan.id)}>Recalcular</button>
          </div>
          <ScheduleTable plan={plan.data} />
        </div>
      )}
    </>
  );
}
