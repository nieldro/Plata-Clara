import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";

type Suggestion = {
  note: string; key: string; account_id: number; account_name: string; kind: "income" | "expense"; amount: number | string;
  frequency: "weekly" | "biweekly" | "monthly"; occurrences: number; last_date: string; start_date: string; category_id: number | null;
};

const FREQ = { weekly: "cada semana", biweekly: "cada 15 días", monthly: "cada mes" };

export default function RecurringSuggestions({ onCreated }: { onCreated: () => void }) {
  const [items, setItems] = useState<Suggestion[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => api.get<Suggestion[]>("/recurring/suggestions").then(setItems).catch(() => setItems([])), []);
  useEffect(() => { load(); }, [load]);

  const idOf = (s: Suggestion) => `${s.account_id}-${s.kind}-${s.key}`;
  const visible = items.filter((s) => !hidden.has(idOf(s)));
  if (visible.length === 0) return null;

  async function accept(s: Suggestion) {
    setBusy(idOf(s));
    setError("");
    try {
      await api.post("/recurring", {
        account_id: s.account_id, category_id: s.category_id, kind: s.kind, amount: Number(s.amount), note: s.note,
        frequency: s.frequency, start_date: s.start_date, // la próxima vez que toca: no se registra nada atrasado
      });
      await load();
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="card">
      <h2>Parece que se repiten</h2>
      <p className="empty">Encontré movimientos que ocurren con regularidad en tu historial. Conviértelos en recurrentes y se registrarán solos (y los verás en «Próximos 30 días»).</p>
      <table>
        <tbody>
          {visible.map((s) => (
            <tr key={idOf(s)}>
              <td>{s.note}<small className="block">{s.account_name} · {s.occurrences} veces, la última el {s.last_date}</small></td>
              <td>{FREQ[s.frequency]}<small className="block">próxima: {s.start_date}</small></td>
              <td className={`num ${s.kind === "income" ? "pos" : "neg"}`}>{s.kind === "income" ? "+" : "−"}{money(s.amount)}</td>
              <td className="actions">
                <button disabled={busy === idOf(s)} onClick={() => accept(s)}>{busy === idOf(s) ? "…" : "Crear recurrente"}</button>
                <button className="link" aria-label={`Ocultar la sugerencia ${s.note}`} title="No es recurrente"
                  onClick={() => setHidden(new Set([...hidden, idOf(s)]))}>✕</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
