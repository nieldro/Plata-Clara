import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { api, money } from "../api";
import { GOLD, MUTED, tooltipStyle } from "../theme";

type Data = {
  days_elapsed: number; income: number | string; expense: number | string; transactions: number;
  previous_expense: number | string; expense_change_pct: number | null; daily_average: number | string;
  daily: { date: string; expense: number | string; future: boolean }[];
  top_categories: { category: string; total: number | string }[];
  biggest_expense: { date: string; amount: number | string; note: string; category: string } | null;
};

const DAY = ["L", "M", "X", "J", "V", "S", "D"];
const short = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short" });

export default function WeeklyCard() {
  const [data, setData] = useState<Data | null>(null);
  useEffect(() => { api.get<Data>("/insights/weekly").then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;

  const chart = data.daily.map((d, i) => ({ label: DAY[i], date: d.date, gasto: Number(d.expense), future: d.future }));
  const change = data.expense_change_pct;

  return (
    <div className="card">
      <h2>Tu semana</h2>
      {data.transactions === 0 ? (
        <p className="empty">Todavía no hay movimientos esta semana.</p>
      ) : (
        <>
          <p className="empty">
            Llevas <b className="neg">{money(data.expense)}</b> en gastos
            {Number(data.income) > 0 && <> y <b className="pos">{money(data.income)}</b> de ingresos</>}
            {" "}({money(data.daily_average)} por día).
            {change !== null && (
              <> Frente a los mismos días de la semana pasada, gastas{" "}
                <b className={change > 0 ? "neg" : "pos"}>{change === 0 ? "lo mismo" : `${Math.abs(change)}% ${change > 0 ? "más" : "menos"}`}</b>
                {" "}({money(data.previous_expense)}).</>
            )}
          </p>
          <div className="chart small">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <XAxis dataKey="label" stroke={MUTED} tickLine={false} axisLine={false} fontSize={12} />
                <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} labelFormatter={(_, p) => (p?.[0]?.payload?.date ? short(p[0].payload.date) : "")} />
                <Bar dataKey="gasto" name="Gasto" radius={[4, 4, 0, 0]}>
                  {chart.map((c) => <Cell key={c.date} fill={c.future ? "rgba(255,255,255,.08)" : GOLD} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {data.biggest_expense && (
            <p className="empty">
              Lo más grande: <b>{money(data.biggest_expense.amount)}</b>
              {data.biggest_expense.note && <> en «{data.biggest_expense.note}»</>} ({data.biggest_expense.category}, {short(data.biggest_expense.date)}).
            </p>
          )}
          {data.top_categories.length > 0 && (
            <p className="empty">Donde más se fue: {data.top_categories.map((c, i) => <span key={c.category}>{i > 0 && " · "}<b>{c.category}</b> {money(c.total)}</span>)}.</p>
          )}
        </>
      )}
    </div>
  );
}
