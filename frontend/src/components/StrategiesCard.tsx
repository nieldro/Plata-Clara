import { useEffect, useState } from "react";
import { api, money } from "../api";

type Result = {
  finished: boolean; months: number | null; total_interest: number | string;
  order: { id: number; name: string; paid_in_month: number | null }[];
};
type Data = {
  monthly_budget: number | string; minimums_total: number | string;
  avalanche: Result; snowball: Result; minimums_only: Result;
  interest_saved_by_avalanche: number | string | null; recommended: "avalanche" | "snowball";
  debts: { id: number; name: string; balance: number; rate_pct: number; minimum: number }[];
};

const months = (m: number | null) => (m === null ? "Nunca (los pagos no cubren los intereses)" : m === 1 ? "1 mes" : `${m} meses`);

function Column({ title, hint, r, best }: { title: string; hint: string; r: Result; best: boolean }) {
  return (
    <div className={`strategy ${best ? "best" : ""}`}>
      {best && <span className="pill">Recomendada</span>}
      <h3>{title}</h3>
      <small className="block">{hint}</small>
      <p className="s-big">{months(r.months)}</p>
      <p className="empty">Intereses en total: <b className="neg">{money(r.total_interest)}</b></p>
      <ol>
        {r.order.map((d) => <li key={d.id}>{d.name}{d.paid_in_month ? <small> · mes {d.paid_in_month}</small> : <small> · no se salda</small>}</li>)}
      </ol>
    </div>
  );
}

export default function StrategiesCard({ debtCount }: { debtCount: number }) {
  const [extra, setExtra] = useState(0);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (debtCount === 0) return setData(null);
    const t = setTimeout(() => {
      api.get<Data>(`/debts/strategies?extra=${extra || 0}`).then((d) => { setData(d); setError(""); })
        .catch((e) => { setData(null); setError(e.message); });
    }, 300);
    return () => clearTimeout(t);
  }, [extra, debtCount]);

  if (debtCount === 0) return null;

  return (
    <div className="card">
      <h2>¿Qué deuda pagar primero?</h2>
      <p className="empty">
        Compara dos formas de usar tu plata: la <b>avalancha</b> ataca primero la deuda con más interés (paga menos en total) y la{" "}
        <b>bola de nieve</b> la de menor saldo (te motiva saldando deudas rápido).
      </p>
      <div className="row">
        <label className="field">¿Cuánto puedes pagar de más cada mes?
          <input type="number" min="0" step="10000" value={extra} onChange={(e) => setExtra(Math.max(0, Number(e.target.value)))} />
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <p className="empty">Presupuesto mensual: <b>{money(data.monthly_budget)}</b> (mínimos {money(data.minimums_total)} + extra {money(Number(data.monthly_budget) - Number(data.minimums_total))}).</p>
          <div className="strategies">
            <Column title="Avalancha" hint="Primero la de mayor interés" r={data.avalanche} best={data.recommended === "avalanche"} />
            <Column title="Bola de nieve" hint="Primero la de menor saldo" r={data.snowball} best={data.recommended === "snowball"} />
            <Column title="Solo mínimos" hint="Sin reasignar lo que se libera" r={data.minimums_only} best={false} />
          </div>
          {data.interest_saved_by_avalanche !== null && Number(data.interest_saved_by_avalanche) > 0 && (
            <p className="hint">La avalancha te ahorra <b>{money(data.interest_saved_by_avalanche)}</b> en intereses frente a la bola de nieve.</p>
          )}
          {data.interest_saved_by_avalanche !== null && Number(data.interest_saved_by_avalanche) === 0 && (
            <p className="hint">Con tus deudas actuales las dos estrategias cuestan lo mismo: elige la que más te motive.</p>
          )}
        </>
      )}
    </div>
  );
}
