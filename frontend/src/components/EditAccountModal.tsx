import { motion } from "framer-motion";
import { FormEvent, useEffect, useState } from "react";
import { Account, api, Debt } from "../api";
import useEscape from "../hooks/useEscape";
import { EASE } from "../theme";

type Props = { account: Account; onClose: () => void; onSaved: () => void };

export default function EditAccountModal({ account, onClose, onSaved }: Props) {
  useEscape(onClose);
  const isCard = account.type === "credit_card";
  const [debt, setDebt] = useState<Debt | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // La tasa, el pago y el día de pago de una tarjeta viven en su deuda: se cargan para mostrarlos.
  useEffect(() => {
    if (isCard && account.debt_id) api.get<Debt[]>("/debts").then((ds) => setDebt(ds.find((d) => d.id === account.debt_id) ?? null));
  }, [isCard, account.debt_id]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const num = (k: string) => (f.get(k) === "" || f.get(k) === null ? null : Number(f.get(k)));
    const body: Record<string, unknown> = { name: String(f.get("name") ?? "").trim() };
    if (isCard) {
      Object.assign(body, {
        credit_limit: num("limit"), rate: num("rate") ?? 0, rate_type: f.get("rate_type"),
        monthly_payment: num("payment"), due_day: num("due_day"),
      });
    } else {
      body.initial_balance = num("balance") ?? 0;
    }
    setBusy(true);
    setError("");
    try {
      await api.patch(`/accounts/${account.id}`, body);
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
      <motion.form className="card modal" onSubmit={submit} key={debt?.id ?? "x"}
        initial={{ opacity: 0, y: 30, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }} transition={{ duration: 0.5, ease: EASE }}>
        <h2>Editar cuenta</h2>
        <label className="field">Nombre
          <input name="name" defaultValue={account.name} required maxLength={100} autoFocus />
        </label>
        {!isCard && (
          <label className="field">Saldo inicial
            <input name="balance" type="number" step="0.01" defaultValue={Number(account.initial_balance)} />
            <small>Con cuánto abriste la cuenta. El saldo actual suma tus movimientos a este valor.</small>
          </label>
        )}
        {isCard && (
          <>
            <label className="field">Cupo total
              <input name="limit" type="number" step="0.01" min="0.01" defaultValue={account.credit_limit ? Number(account.credit_limit) : ""} required />
            </label>
            <div className="row">
              <label className="field">Tasa %
                <input name="rate" type="number" step="0.01" min="0" defaultValue={debt ? Number(debt.rate) : ""} />
              </label>
              <label className="field">Tipo de tasa
                <select name="rate_type" defaultValue={debt?.rate_type ?? "EA"}>
                  <option value="EA">Efectiva anual</option>
                  <option value="MV">Mensual vencida</option>
                  <option value="NA">Nominal anual</option>
                </select>
              </label>
            </div>
            <div className="row">
              <label className="field">Pago mensual habitual
                <input name="payment" type="number" step="0.01" min="0" defaultValue={debt?.monthly_payment ? Number(debt.monthly_payment) : ""} />
              </label>
              <label className="field">Día de pago (1-31)
                <input name="due_day" type="number" min="1" max="31" defaultValue={debt?.due_day ?? ""} />
              </label>
            </div>
          </>
        )}
        {error && <p className="error">{error}</p>}
        <div className="row modal-actions">
          <button type="button" className="link" onClick={onClose}>Cancelar</button>
          <button disabled={busy}>{busy ? "…" : "Guardar cambios"}</button>
        </div>
      </motion.form>
    </motion.div>
  );
}
