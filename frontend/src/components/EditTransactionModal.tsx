import { motion } from "framer-motion";
import { FormEvent, useState } from "react";
import { Account, api, Category, splitTags, Tx } from "../api";
import { EASE } from "../theme";
import TagInput from "./TagInput";

type Props = {
  tx: Tx;
  accounts: Account[];
  cats: Category[];
  suggestions?: string[];
  onClose: () => void;
  onSaved: () => void;
};

export default function EditTransactionModal({ tx, accounts, cats, suggestions, onClose, onSaved }: Props) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const category = f.get("category") ? Number(f.get("category")) : null;
    setBusy(true);
    setError("");
    try {
      await api.patch(`/transactions/${tx.id}`, {
        account_id: Number(f.get("account")),
        kind: f.get("kind"),
        amount: Number(f.get("amount")),
        date: f.get("date"),
        note: String(f.get("note") ?? ""),
        tags: splitTags(f.get("tags")),
        category_id: category,
        clear_category: category === null,
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div className="modal-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.form className="card modal" onSubmit={submit}
        initial={{ opacity: 0, y: 30, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }} transition={{ duration: 0.5, ease: EASE }}>
        <h2>Editar movimiento</h2>
        <select name="kind" defaultValue={tx.kind}>
          <option value="expense">Gasto</option>
          <option value="income">Ingreso / abono</option>
        </select>
        <input name="amount" type="number" step="0.01" min="0.01" defaultValue={Number(tx.amount)} required />
        <select name="account" defaultValue={tx.account_id} required>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select name="category" defaultValue={tx.category_id ?? ""}>
          <option value="">Sin categoría</option>
          {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input name="date" type="date" defaultValue={tx.date} required />
        <input name="note" defaultValue={tx.note} placeholder="Nota" maxLength={255} />
        <TagInput initial={tx.tags} suggestions={suggestions} />
        {error && <p className="error">{error}</p>}
        <div className="row modal-actions">
          <button type="button" className="link" onClick={onClose}>Cancelar</button>
          <button disabled={busy}>{busy ? "…" : "Guardar cambios"}</button>
        </div>
      </motion.form>
    </motion.div>
  );
}
