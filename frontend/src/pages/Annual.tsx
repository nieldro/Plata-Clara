import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { api, localDate, money } from "../api";
import CountUp from "../components/CountUp";
import { monthName, monthShort } from "../dates";
import { GOLD, MUTED, NEG, tooltipStyle } from "../theme";

type Month = { month: string; income: number | string; expense: number | string; net: number | string };
type Data = {
  year: number; income: number | string; expense: number | string; net: number | string; savings_rate: number | null;
  active_months: number; avg_monthly_expense: number | string; best_month: string | null; worst_month: string | null;
  months: Month[]; top_categories: { category: string; total: number | string; pct: number }[];
};

export default function Annual() {
  const thisYear = Number(localDate().slice(0, 4));
  const [year, setYear] = useState(thisYear);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    api.get<Data>(`/insights/annual?year=${year}`).then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message));
  }, [year]);

  const chart = data?.months.map((m) => ({ label: monthShort(m.month), Ingresos: Number(m.income), Gastos: Number(m.expense) })) ?? [];
  const tiles = data ? [
    { label: "Ingresos del año", value: Number(data.income), cls: "pos" },
    { label: "Gastos del año", value: Number(data.expense), cls: "neg" },
    { label: "Ahorraste", value: Number(data.net), cls: Number(data.net) < 0 ? "neg" : "pos" },
  ] : [];

  return (
    <>
      <div className="card">
        <div className="month-nav">
          <button className="link" onClick={() => setYear(year - 1)} aria-label="Año anterior">←</button>
          <h2>{year}</h2>
          <button className="link" disabled={year >= thisYear} onClick={() => setYear(year + 1)} aria-label="Año siguiente">→</button>
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      {data && data.active_months === 0 && <p className="empty">No hay movimientos en {year}.</p>}

      {data && data.active_months > 0 && (
        <>
          <div className="tiles">
            {tiles.map((t) => (
              <div className="card tile" key={t.label}><small>{t.label}</small><b className={t.cls}><CountUp value={t.value} format={(n) => money(n)} /></b></div>
            ))}
            <div className="card tile"><small>Tasa de ahorro</small><b>{data.savings_rate === null ? "—" : `${data.savings_rate}%`}</b></div>
          </div>

          <div className="card">
            <h2>Mes a mes</h2>
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(255,255,255,.06)" vertical={false} />
                  <XAxis dataKey="label" stroke={MUTED} tickLine={false} axisLine={false} fontSize={12} />
                  <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} />
                  <Legend wrapperStyle={{ color: MUTED, fontSize: 12 }} />
                  <Bar dataKey="Ingresos" fill={GOLD} radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Gastos" fill={NEG} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="empty">
              Gastas en promedio <b>{money(data.avg_monthly_expense)}</b> al mes ({data.active_months} {data.active_months === 1 ? "mes" : "meses"} con movimientos).
              {data.best_month && <> Tu mejor mes fue <b className="pos">{monthName(data.best_month)}</b></>}
              {data.worst_month && data.worst_month !== data.best_month && <> y el más ajustado, <b className="neg">{monthName(data.worst_month)}</b></>}.
            </p>
          </div>

          {data.top_categories.length > 0 && (
            <div className="card">
              <h2>En qué se fue tu plata</h2>
              <ul className="merchants">
                {data.top_categories.map((c) => (
                  <li key={c.category}>
                    <div className="m-top"><span>{c.category}</span><b>{money(c.total)}</b></div>
                    <div className="bar thin"><i style={{ width: `${c.pct}%` }} /></div>
                    <small>{c.pct}% de tus gastos</small>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </>
  );
}
