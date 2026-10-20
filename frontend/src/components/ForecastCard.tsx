import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, money } from "../api";
import { GOLD, MUTED, NEG, tooltipStyle } from "../theme";

type Point = { date: string; balance: number | string };
type Data = {
  days: number; start: number | string; end: number | string; will_run_short: boolean;
  first_negative_date: string | null; lowest: { date: string; balance: number | string };
  unknown_amounts: number; overdue_excluded: number; series: Point[];
};

const RANGES = [30, 60, 90];
const short = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short" });

export default function ForecastCard() {
  const [days, setDays] = useState(60);
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => { api.get<Data>(`/forecast?days=${days}`).then(setData).catch(() => setData(null)); }, [days]);
  if (!data) return null;

  const points = data.series.map((p) => ({ ...p, balance: Number(p.balance), label: short(p.date) }));
  const flat = points.every((p) => p.balance === points[0].balance);

  return (
    <div className="card">
      <div className="budget-head">
        <h2>Tu dinero en los próximos días</h2>
        <span className="range">
          {RANGES.map((r) => (
            <button key={r} className={`link ${r === days ? "on" : ""}`} onClick={() => setDays(r)}>{r} d</button>
          ))}
        </span>
      </div>

      {data.will_run_short ? (
        <p className="warn-line">
          ⚠️ Según lo programado, tu dinero quedaría en negativo el <b>{short(data.first_negative_date!)}</b>
          {" "}(punto más bajo: <b className="neg">{money(data.lowest.balance)}</b>). Revisa esos pagos o mueve dinero antes.
        </p>
      ) : (
        <p className="empty">
          Hoy tienes <b>{money(data.start)}</b> y, con lo programado, en {days} días tendrás <b>{money(data.end)}</b>.
          Tu punto más bajo será <b>{money(data.lowest.balance)}</b>.
        </p>
      )}

      {flat ? (
        <p className="empty">No hay pagos ni cobros programados en este período, así que tu dinero no cambia. Agrega recurrentes o el día de pago de tus tarjetas para ver la proyección.</p>
      ) : (
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="fc" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor={GOLD} stopOpacity={0.35} /><stop offset="1" stopColor={GOLD} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,.06)" vertical={false} />
              <XAxis dataKey="label" stroke={MUTED} tickLine={false} axisLine={false} fontSize={11} minTickGap={36} />
              <YAxis hide domain={["auto", "auto"]} />
              <Tooltip {...tooltipStyle} formatter={(v) => money(Number(v))} />
              <ReferenceLine y={0} stroke={NEG} strokeDasharray="4 4" />
              <Area name="Dinero" dataKey="balance" type="stepAfter" stroke={GOLD} strokeWidth={2} fill="url(#fc)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {(data.unknown_amounts > 0 || data.overdue_excluded > 0) && (
        <small className="note">
          {data.unknown_amounts > 0 && `${data.unknown_amounts} pago(s) sin monto no se cuentan. `}
          {data.overdue_excluded > 0 && `${data.overdue_excluded} cobro(s) vencido(s) no se cuentan.`}
        </small>
      )}
    </div>
  );
}
