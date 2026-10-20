import { FormEvent, useState } from "react";
import { Account, api, Category, confirmIfDuplicate, money, splitTags } from "../api";

type Parsed = {
  ready: boolean; amount: number | string | null; kind: "income" | "expense"; date: string; note: string; tags: string[];
  account_id: number | null; account_name: string | null; category_id: number | null; category_confidence: number | null;
  warnings: string[];
};
type Draft = { amount: string; kind: "income" | "expense"; date: string; accountId: string; categoryId: string; note: string; tags: string };

const EXAMPLES = "café 4.500 ayer con nequi · uber 12 mil #trabajo · nómina 3.000.000";

export default function QuickAdd({ accounts, cats, onCreated }: { accounts: Account[]; cats: Category[]; onCreated: () => void }) {
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (accounts.length === 0) return null;
  const set = (patch: Partial<Draft>) => setDraft((d) => (d ? { ...d, ...patch } : d));

  async function understand(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      const p = await api.post<Parsed>("/quick-add/parse", { text });
      setParsed(p);
      setDraft({
        amount: p.amount === null ? "" : String(Number(p.amount)), kind: p.kind, date: p.date,
        accountId: p.account_id ? String(p.account_id) : "", categoryId: p.category_id ? String(p.category_id) : "",
        note: p.note, tags: p.tags.join(", "),
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError("");
    const ok = await confirmIfDuplicate({ account_id: Number(draft.accountId), amount: Number(draft.amount), date: draft.date, kind: draft.kind });
    if (!ok) return setBusy(false);
    try {
      await api.post("/transactions", {
        account_id: Number(draft.accountId), category_id: draft.categoryId ? Number(draft.categoryId) : null,
        kind: draft.kind, amount: Number(draft.amount), date: draft.date, note: draft.note, tags: splitTags(draft.tags),
      });
      cancel();
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function cancel() { setText(""); setParsed(null); setDraft(null); setError(""); }

  const canSave = draft && Number(draft.amount) > 0 && draft.accountId && draft.date;

  return (
    <div className="card quick">
      <h2>Registro rápido</h2>
      <form className="row" onSubmit={understand}>
        <input className="grow" value={text} onChange={(e) => setText(e.target.value)} maxLength={300}
          placeholder="Escribe como hablas: café 4.500 ayer con nequi" aria-label="Describe el movimiento" />
        <button disabled={busy || !text.trim()}>{busy && !draft ? "…" : "Entender"}</button>
      </form>
      {!draft && <small className="note">{EXAMPLES}</small>}
      {error && <p className="error">{error}</p>}

      {draft && parsed && (
        <div className="quick-preview">
          {parsed.warnings.map((w) => <p className="warn-line" key={w}>{w}</p>)}
          <p className="empty">Revisa y corrige lo que haga falta antes de guardar:</p>
          <div className="row">
            <select value={draft.kind} onChange={(e) => set({ kind: e.target.value as Draft["kind"], categoryId: "" })}>
              <option value="expense">Gasto</option><option value="income">Ingreso</option>
            </select>
            <input type="number" min="0.01" step="0.01" value={draft.amount} placeholder="Monto" onChange={(e) => set({ amount: e.target.value })} />
            <select value={draft.accountId} onChange={(e) => set({ accountId: e.target.value })}>
              <option value="">¿Qué cuenta?</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <select value={draft.categoryId} onChange={(e) => set({ categoryId: e.target.value })}>
              <option value="">Sin categoría</option>
              {cats.filter((c) => c.kind === draft.kind).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="row">
            <input type="date" value={draft.date} onChange={(e) => set({ date: e.target.value })} />
            <input value={draft.note} placeholder="Nota" maxLength={255} onChange={(e) => set({ note: e.target.value })} />
            <input value={draft.tags} placeholder="Etiquetas (separadas por coma)" onChange={(e) => set({ tags: e.target.value })} />
          </div>
          {parsed.category_id && draft.categoryId === String(parsed.category_id) && (
            <small className="note">✨ Categoría sugerida por lo que has categorizado antes.</small>
          )}
          <div className="row modal-actions">
            <button type="button" className="link" onClick={cancel}>Descartar</button>
            <button disabled={busy || !canSave} onClick={save}>
              {busy ? "…" : canSave ? `Guardar ${draft.kind === "income" ? "+" : "−"}${money(Number(draft.amount))}` : "Completa monto y cuenta"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
