import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Account, api, Debt, download, localMonth, money } from "../api";
import CountUp from "../components/CountUp";
import ForecastCard from "../components/ForecastCard";
import MerchantsCard from "../components/MerchantsCard";
import NetWorthCard from "../components/NetWorthCard";
import OnboardingCard from "../components/OnboardingCard";
import UpcomingCard from "../components/UpcomingCard";
import WeeklyCard from "../components/WeeklyCard";
import { GOLD, MUTED, NEG, PIE_COLORS, tooltipStyle } from "../theme";

type Summary = {
  income: number; expense: number; net: number;
  expense_by_category: { category: string; total: number }[];
};
type TrendPoint = { month: string; income: number; expense: number };

const monthLabel = (m: string) =>
  new Date(Number(m.slice(0, 4)), Number(m.slice(5)) - 1).toLocaleDateString("es-CO", { month: "short" });

export default function Dashboard() {
  const month = localMonth();
  const [s, setS] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [debts, setDebts] = useState<Debt[]>([]);
  const [reportMonth, setReportMonth] = useState(month);
  const [reporting, setReporting] = useState(false);
  const [reportError, setReportError] = useState("");

  async function downloadReport() {
    setReporting(true);
    setReportError("");
    try {
      await download(`/reports/monthly?month=${reportMonth}`, `plata-clara-informe-${reportMonth}.pdf`);
    } catch (err) {
      setReportError((err as Error).message);
    } finally {
      setReporting(false);
    }
  }

  useEffect(() => {
    api.get<Summary>(`/summary?month=${month}`).then(setS);
    api.get<TrendPoint[]>("/summary/trend?months=6").then(setTrend);
    api.get<Account[]>("/accounts").then(setAccounts);
    api.get<Debt[]>("/debts").then(setDebts);
  }, [month]);

  // Las tarjetas ya cuentan como deuda (vía /debts); aquí solo el dinero propio.
  const cash = accounts.filter((x) => x.type !== "credit_card").reduce((a, x) => a + Number(x.balance), 0);
  const owed = debts.reduce((a, x) => a + Number(x.current_balance), 0);
  const fmt = (n: number) => money(n);

  const tiles: { label: string; value: number; cls?: string }[] = [
    { label: "Ingresos del mes", value: Number(s?.income ?? 0), cls: "pos" },
    { label: "Gastos del mes", value: Number(s?.expense ?? 0), cls: "neg" },
    { label: "Dinero en cuentas", value: cash },
    { label: "Total que debes", value: owed, cls: "neg" },
    { label: "Patrimonio neto", value: cash - owed },
  ];
  const cats = (s?.expense_by_category ?? []).map((c) => ({ name: c.category, value: Number(c.total) }));
  const data = trend.map((t) => ({ ...t, label: monthLabel(t.month) }));

  return (
    <>
      <OnboardingCard />
      <div className="tiles">
        {tiles.map((t) => (
          <div className="card tile" key={t.label}>
            <small>{t.label}</small>
            <b className={t.cls}><CountUp value={t.value} format={fmt} /></b>
          </div>
        ))}
      </div>

      <div className="card report-card">
        <div>
          <h2>Informe mensual</h2>
          <p className="empty">Un PDF listo para imprimir o guardar: resumen, gasto por categoría con tus presupuestos, mayores gastos y patrimonio.</p>
        </div>
        <div className="report-actions">
          <input type="month" value={reportMonth} max={month} onChange={(e) => e.target.value && setReportMonth(e.target.value)} aria-label="Mes del informe" />
          <button disabled={reporting} onClick={downloadReport}>{reporting ? "Generando…" : "⬇ Descargar PDF"}</button>
        </div>
        {reportError && <p className="error">{reportError}</p>}
      </div>

      <WeeklyCard />
      <ForecastCard />
      <UpcomingCard />
      <NetWorthCard />
      <MerchantsCard month={month} />

      <div className="two">
        <div className="card">
          <h2>Ingresos y gastos · 6 meses</h2>
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <defs>
                  <linearGradient id="inc" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor={GOLD} stopOpacity={0.4} /><stop offset="1" stopColor={GOLD} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="exp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor={NEG} stopOpacity={0.3} /><stop offset="1" stopColor={NEG} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,.06)" vertical={false} />
                <XAxis dataKey="label" stroke={MUTED} tickLine={false} axisLine={false} fontSize={12} />
                <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} />
                <Area name="Ingresos" dataKey="income" stroke={GOLD} strokeWidth={2} fill="url(#inc)" animationDuration={1400} />
                <Area name="Gastos" dataKey="expense" stroke={NEG} strokeWidth={2} fill="url(#exp)" animationDuration={1400} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h2>Gasto por categoría</h2>
          {cats.length === 0 ? (
            <p className="empty">Aún no hay gastos este mes. Registra el primero en «Movimientos».</p>
          ) : (
            <>
              <div className="chart small">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={cats} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="90%" paddingAngle={3} stroke="none" animationDuration={1200}>
                      {cats.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="legend">
                {cats.map((c, i) => (
                  <li key={c.name}>
                    <i style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                    <span>{c.name}</span><b>{money(c.value)}</b>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  );
}
