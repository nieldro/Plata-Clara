import { useEffect, useState } from "react";
import { api, money } from "../api";

type Item = {
  date: string; days: number; kind: "income" | "expense"; title: string; amount: number | string | null;
  source: "recurring" | "debt" | "loan"; overdue?: boolean;
};
type Data = { days: number; to_pay: number | string; to_receive: number | string; items: Item[] };

const SOURCE: Record<Item["source"], string> = { recurring: "Recurrente", debt: "Tarjeta o crédito", loan: "Préstamo" };

const when = (i: Item) =>
  i.overdue ? `Venció hace ${-i.days} ${-i.days === 1 ? "día" : "días"}`
    : i.days === 0 ? "Hoy" : i.days === 1 ? "Mañana" : `En ${i.days} días`;

const SHOWN = 8;

export default function UpcomingCard({ days = 30 }: { days?: number }) {
  const [data, setData] = useState<Data | null>(null);
  const [all, setAll] = useState(false);

  useEffect(() => { api.get<Data>(`/upcoming?days=${days}`).then(setData).catch(() => setData(null)); }, [days]);

  if (!data) return null;
  const items = all ? data.items : data.items.slice(0, SHOWN);

  return (
    <div className="card">
      <h2>Próximos {days} días</h2>
      {data.items.length === 0 ? (
        <p className="empty">No tienes pagos ni cobros programados. Agrega recurrentes, el día de pago de tus tarjetas o la fecha límite de un préstamo y aparecerán aquí.</p>
      ) : (
        <>
          <p className="empty">
            Por pagar <b className="neg">{money(data.to_pay)}</b> · por recibir <b className="pos">{money(data.to_receive)}</b>
            {data.items.some((i) => i.amount === null) && " · hay pagos sin monto definido"}
          </p>
          <table>
            <tbody>
              {items.map((i, n) => (
                <tr key={`${i.source}-${i.date}-${i.title}-${n}`}>
                  <td className={i.overdue ? "neg" : ""}>{when(i)}<small className="block">{i.date}</small></td>
                  <td>{i.title}<small className="block">{SOURCE[i.source]}</small></td>
                  <td className={`num ${i.kind === "income" ? "pos" : "neg"}`}>
                    {i.amount === null ? "—" : `${i.kind === "income" ? "+" : "−"}${money(i.amount)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.items.length > SHOWN && (
            <button className="link" onClick={() => setAll(!all)}>{all ? "Ver menos" : `Ver los ${data.items.length}`}</button>
          )}
        </>
      )}
    </div>
  );
}
