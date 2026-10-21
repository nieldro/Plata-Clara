import { useCallback, useEffect, useState } from "react";
import { api, money } from "../api";

type Item = {
  category_id: number; category: string; average: number | string; suggested: number; has_budget: boolean;
  current_budget: number | string | null;
};
type Data = { months: number; items: Item[] };

export default function BudgetSuggestions({ onApplied }: { onApplied: () => void }) {
  const [data, setData] = useState<Data | null>(null);
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    const d = await api.get<Data>("/budgets/suggestions?months=3");
    setData(d);
    setAmounts(Object.fromEntries(d.items.map((i) => [i.category_id, String(i.suggested)])));
    setPicked(new Set(d.items.filter((i) => !i.has_budget).map((i) => i.category_id))); // por defecto, solo lo que aún no tiene tope
  }, []);
  useEffect(() => { load().catch(() => setData(null)); }, [load]);

  if (!data || data.items.length === 0) return null;
  const toggle = (id: number) => setPicked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const chosen = data.items.filter((i) => picked.has(i.category_id) && Number(amounts[i.category_id]) > 0);

  async function apply() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<{ created: number; updated: number }>("/budgets/suggestions/apply", {
        items: chosen.map((i) => ({ category_id: i.category_id, amount: Number(amounts[i.category_id]) })),
      });
      setMsg({ ok: true, text: `Listo: ${r.created} creado(s) y ${r.updated} actualizado(s).` });
      onApplied();
      await load();
    } catch (err) {
      setMsg({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Presupuestos sugeridos</h2>
      <p className="empty">
        Según el promedio de tus últimos {data.months} meses completos (con 5 % de holgura). Ajusta los montos que quieras y crea varios de una vez.
      </p>
      <table>
        <thead><tr><th /><th>Categoría</th><th className="num">Promedio mensual</th><th className="num">Tope</th></tr></thead>
        <tbody>
          {data.items.map((i) => (
            <tr key={i.category_id}>
              <td className="check-col"><input type="checkbox" checked={picked.has(i.category_id)} onChange={() => toggle(i.category_id)} aria-label={`Incluir ${i.category}`} /></td>
              <td>{i.category}{i.has_budget && <small className="block">Ya tiene tope: {money(i.current_budget ?? 0)}</small>}</td>
              <td className="num">{money(i.average)}</td>
              <td className="num">
                <input className="amount-input" type="number" min="1" step="10000" value={amounts[i.category_id] ?? ""}
                  onChange={(e) => setAmounts({ ...amounts, [i.category_id]: e.target.value })} aria-label={`Tope para ${i.category}`} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row modal-actions">
        {msg && <span className={msg.ok ? "ok-msg" : "error"} role="status">{msg.text}</span>}
        <button disabled={busy || chosen.length === 0} onClick={apply}>{busy ? "…" : `Crear ${chosen.length} presupuesto${chosen.length === 1 ? "" : "s"}`}</button>
      </div>
    </div>
  );
}
