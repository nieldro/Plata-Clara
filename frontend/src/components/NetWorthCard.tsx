import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money } from "../api";
import { GOLD, MUTED, tooltipStyle } from "../theme";
import useCardData from "../hooks/useCardData";
import CardSkeleton from "./CardSkeleton";

type Point = { month: string; cash: number | string; debt: number | string; net_worth: number | string; estimated: boolean };
type Data = { months: number; change: number | string; points: Point[] };

const label = (m: string) => new Date(Number(m.slice(0, 4)), Number(m.slice(5)) - 1).toLocaleDateString("es-CO", { month: "short", year: "2-digit" });
const RANGES = [6, 12, 24];

export default function NetWorthCard() {
  const [months, setMonths] = useState(12);
  const { data, loading } = useCardData<Data>(`/net-worth?months=${months}`);
  if (!data) return loading ? <CardSkeleton lines={4} /> : null;

  const points = data.points.map((p) => ({ ...p, label: label(p.month), net: Number(p.net_worth), cash: Number(p.cash), debt: Number(p.debt) }));
  const last = points[points.length - 1];
  const change = Number(data.change);

  return (
    <div className="card">
      <div className="budget-head">
        <h2>Tu patrimonio en el tiempo</h2>
        <span className="range">{RANGES.map((r) => <button key={r} className={`link ${r === months ? "on" : ""}`} onClick={() => setMonths(r)}>{r} m</button>)}</span>
      </div>
      <p className="empty">
        Hoy: <b>{money(last.net)}</b> ({money(last.cash)} en cuentas − {money(last.debt)} de deudas).
        {points.length > 1 && (
          <> En {points.length - 1} {points.length - 1 === 1 ? "mes" : "meses"} {change >= 0 ? "creció" : "bajó"} <b className={change >= 0 ? "pos" : "neg"}>{money(Math.abs(change))}</b>.</>
        )}
      </p>
      {points.length < 2 ? (
        <p className="empty">Con más meses de movimientos verás aquí cómo evoluciona.</p>
      ) : (
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor={GOLD} stopOpacity={0.35} /><stop offset="1" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,.06)" vertical={false} />
              <XAxis dataKey="label" stroke={MUTED} tickLine={false} axisLine={false} fontSize={11} minTickGap={24} />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} />
              <Area name="Patrimonio" dataKey="net" stroke={GOLD} strokeWidth={2} fill="url(#nw)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      <small className="note">Las deudas de meses pasados son una estimación: se calculan deshaciendo desde hoy tus compras y pagos. No incluye préstamos a personas.</small>
    </div>
  );
}
