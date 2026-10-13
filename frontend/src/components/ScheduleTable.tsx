import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { money, Plan } from "../api";
import { GOLD, IVORY, MUTED, tooltipStyle } from "../theme";

export default function ScheduleTable({ plan }: { plan: Plan }) {
  return (
    <>
      <div className="facts">
        {plan.payment !== undefined && <div><small>Cuota</small><b>{money(plan.payment)}</b></div>}
        {plan.monthly_rate_pct !== undefined && <div><small>Tasa mensual</small><b>{plan.monthly_rate_pct}%</b></div>}
        <div><small>Meses</small><b>{plan.months}</b></div>
        <div><small>Intereses totales</small><b className="neg">{money(plan.total_interest)}</b></div>
        <div><small>Total pagado</small><b>{money(plan.total_paid)}</b></div>
        {!!plan.interest_saved && (
          <div><small>Te ahorras</small><b className="pos">{money(plan.interest_saved)} · {plan.months_saved} meses</b></div>
        )}
      </div>

      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={plan.rows} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <XAxis dataKey="n" stroke={MUTED} tickLine={false} axisLine={false} fontSize={12} />
            <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} labelFormatter={(n) => `Mes ${n}`} />
            <Bar name="Capital" dataKey="principal" stackId="a" fill={IVORY} fillOpacity={0.8} animationDuration={1200} />
            <Bar name="Interés" dataKey="interest" stackId="a" fill={GOLD} radius={[3, 3, 0, 0]} animationDuration={1200} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="scroll" data-lenis-prevent>
        <table>
          <thead><tr><th>#</th><th className="num">Pago</th><th className="num">Interés</th><th className="num">Capital</th><th className="num">Saldo</th></tr></thead>
          <tbody>
            {plan.rows.map((r) => (
              <tr key={r.n}>
                <td>{r.n}</td><td className="num">{money(r.payment)}</td><td className="num">{money(r.interest)}</td>
                <td className="num">{money(r.principal)}</td><td className="num">{money(r.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
