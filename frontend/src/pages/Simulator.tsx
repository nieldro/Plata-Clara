import { FormEvent, useState } from "react";
import { api, money, Plan } from "../api";
import ScheduleTable from "../components/ScheduleTable";

const RateType = () => (
  <select name="rate_type">
    <option value="EA">Efectiva anual</option>
    <option value="MV">Mensual vencida</option>
    <option value="NA">Nominal anual</option>
  </select>
);

export default function Simulator() {
  const [loan, setLoan] = useState<Plan | null>(null);
  const [payoff, setPayoff] = useState<Plan | null>(null);
  const [sav, setSav] = useState<{ monthly_contribution: number; total_contributed: number; interest_earned: number } | null>(null);
  const [error, setError] = useState("");

  const run = (path: string, fields: string[], set: (r: any) => void) => async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {};
    fields.forEach((k) => (body[k] = k === "rate_type" ? f.get(k) : Number(f.get(k) || 0)));
    try {
      set(await api.post(path, body));
      setError("");
    } catch (err) {
      set(null);
      setError((err as Error).message);
    }
  };

  return (
    <>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>Simulador de crédito</h2>
        <form className="row" onSubmit={run("/simulator/loan", ["amount", "rate", "rate_type", "months", "extra"], setLoan)}>
          <input name="amount" type="number" placeholder="Monto" required />
          <input name="rate" type="number" step="0.01" placeholder="Tasa %" required />
          <RateType />
          <input name="months" type="number" placeholder="Plazo (meses)" required />
          <input name="extra" type="number" placeholder="Abono extra mensual" />
          <button>Calcular</button>
        </form>
        {loan && <ScheduleTable plan={loan} />}
      </div>

      <div className="card">
        <h2>¿Cuánto tardo en pagar mi tarjeta?</h2>
        <form className="row" onSubmit={run("/simulator/payoff", ["balance", "rate", "rate_type", "payment"], setPayoff)}>
          <input name="balance" type="number" placeholder="Deuda actual" required />
          <input name="rate" type="number" step="0.01" placeholder="Tasa %" required />
          <RateType />
          <input name="payment" type="number" placeholder="Pago mensual" required />
          <button>Calcular</button>
        </form>
        {payoff && <ScheduleTable plan={payoff} />}
      </div>

      <div className="card">
        <h2>Meta de ahorro</h2>
        <form className="row" onSubmit={run("/simulator/savings", ["target", "current", "rate", "rate_type", "months"], setSav)}>
          <input name="target" type="number" placeholder="Meta" required />
          <input name="current" type="number" placeholder="Ya tengo" />
          <input name="rate" type="number" step="0.01" placeholder="Rinde %" />
          <RateType />
          <input name="months" type="number" placeholder="Meses" required />
          <button>Calcular</button>
        </form>
        {sav && (
          <p>
            Ahorra <b className="pos">{money(sav.monthly_contribution)}</b> al mes. Pones {money(sav.total_contributed)}
            {" "}y los intereses aportan {money(sav.interest_earned)}.
          </p>
        )}
      </div>
    </>
  );
}
