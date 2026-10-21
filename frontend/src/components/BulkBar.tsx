import { useState } from "react";
import { api, Category } from "../api";

type Result = { action: string; affected: number; skipped: { id: number; reason: string }[]; not_found: number[] };
type Props = { ids: number[]; cats: Category[]; onDone: () => void; onClear: () => void };

const VERB: Record<string, string> = { delete: "borrados", set_category: "recategorizados", add_tag: "etiquetados", remove_tag: "sin la etiqueta" };

/** Barra que aparece al seleccionar movimientos: categorizar, etiquetar o borrar varios a la vez. */
export default function BulkBar({ ids, cats, onDone, onClear }: Props) {
  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function run(action: string, extra: Record<string, unknown> = {}) {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<Result>("/transactions/bulk", { ids, action, ...extra });
      const why = r.skipped.length ? ` · ${r.skipped.length} omitido(s): ${[...new Set(r.skipped.map((s) => s.reason))].join("; ")}` : "";
      setMsg({ ok: r.affected > 0, text: `${r.affected} ${VERB[action]}${why}` });
      if (r.affected > 0) { setCategory(""); setTag(""); onDone(); }
    } catch (err) {
      setMsg({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const n = ids.length;
  return (
    <div className="bulkbar" role="region" aria-label="Acciones sobre los movimientos seleccionados">
      <b>{n} {n === 1 ? "seleccionado" : "seleccionados"}</b>
      <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Categoría para los seleccionados">
        <option value="">Categoría…</option>
        <option value="none">Sin categoría</option>
        {cats.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.kind === "income" ? "ingreso" : "gasto"})</option>)}
      </select>
      <button disabled={busy || !category} onClick={() => run("set_category", category === "none" ? { clear_category: true } : { category_id: Number(category) })}>Aplicar</button>
      <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="Etiqueta" maxLength={30} aria-label="Etiqueta para los seleccionados" />
      <button className="btn-ghost" disabled={busy || !tag.trim()} onClick={() => run("add_tag", { tag })}>Etiquetar</button>
      <button className="btn-ghost" disabled={busy || !tag.trim()} onClick={() => run("remove_tag", { tag })}>Quitar etiqueta</button>
      <button className="btn-danger" disabled={busy}
        onClick={() => confirm(`¿Borrar ${n} ${n === 1 ? "movimiento" : "movimientos"}? Los saldos de las cuentas se ajustan y no se puede deshacer.`) && run("delete")}>Borrar</button>
      <button className="link" onClick={onClear}>Cancelar</button>
      {msg && <span className={msg.ok ? "ok-msg" : "error"} role="status">{msg.text}</span>}
    </div>
  );
}
