import { AnimatePresence } from "framer-motion";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ACCOUNT_TYPES, Account, api, Category, Institution, loadInstitutions, money, Tx } from "../api";
import AccountModal from "../components/AccountModal";
import InstitutionLogo from "../components/InstitutionLogo";

export default function Transactions() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [txs, setTxs] = useState<Tx[]>([]);
  const [insts, setInsts] = useState<Institution[]>([]);
  const [filter, setFilter] = useState<number | null>(null);
  const [modal, setModal] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setAccounts(await api.get("/accounts"));
    setTxs(await api.get(`/transactions${filter ? `?account_id=${filter}` : ""}`));
  }, [filter]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    loadInstitutions().then(setInsts);
    api.get<Category[]>("/categories").then(setCats);
  }, []);

  const instOf = (a: Account) => insts.find((i) => i.slug === a.institution);
  const entityName = (a: Account) => instOf(a)?.name ?? a.institution_name ?? "Efectivo";
  const acc = (id: number) => accounts.find((a) => a.id === id);
  const catName = (id: number | null) => cats.find((c) => c.id === id)?.name ?? "—";

  async function addTx(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/transactions", {
        account_id: Number(f.get("account")),
        category_id: f.get("category") ? Number(f.get("category")) : null,
        kind: f.get("kind"),
        amount: Number(f.get("amount")),
        date: f.get("date"),
        note: f.get("note") ?? "",
      });
      form.reset();
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeAccount(a: Account) {
    const extra = a.type === "credit_card" ? " También se elimina la deuda de la tarjeta." : "";
    if (!confirm(`¿Eliminar «${a.name}» y todos sus movimientos?${extra}`)) return;
    await api.del(`/accounts/${a.id}`);
    if (filter === a.id) setFilter(null);
    load();
  }

  return (
    <>
      <div className="acc-grid">
        {accounts.map((a) => {
          const isCard = a.type === "credit_card";
          return (
            <div key={a.id} className={`card acc ${filter === a.id ? "sel" : ""}`}
              onClick={() => setFilter(filter === a.id ? null : a.id)}>
              <div className="acc-top">
                <InstitutionLogo inst={instOf(a)} name={entityName(a)} />
                <div className="acc-names">
                  <b>{a.name}</b>
                  <small>{entityName(a)} · {ACCOUNT_TYPES[a.type]}</small>
                </div>
                <button className="link" title="Eliminar cuenta" onClick={(e) => { e.stopPropagation(); removeAccount(a); }}>✕</button>
              </div>
              <div className={`acc-bal ${Number(a.balance) < 0 ? "neg" : ""}`}>{money(a.balance)}</div>
              {isCard && (
                <small>
                  Disponible {a.available !== null ? money(a.available) : "—"}
                  {a.credit_limit ? ` de ${money(a.credit_limit)}` : ""}
                </small>
              )}
            </div>
          );
        })}
        <button className="card acc add" onClick={() => setModal(true)}>
          <span>＋</span>
          <b>Agregar cuenta</b>
          <small>Banco, billetera, inversión o tarjeta</small>
        </button>
      </div>

      <div className="card">
        <h2>Nuevo movimiento</h2>
        {accounts.length === 0 ? (
          <p className="empty">Primero agrega una cuenta (por ejemplo tu Bancolombia, Nequi o Hapi) para registrar movimientos.</p>
        ) : (
          <form className="row" onSubmit={addTx}>
            <select name="kind"><option value="expense">Gasto</option><option value="income">Ingreso / abono</option></select>
            <input name="amount" type="number" step="0.01" min="0.01" placeholder="Monto" required />
            <select name="account" required defaultValue={filter ?? ""}
              onChange={(e) => { if (e.target.value === "new") { e.target.value = ""; setModal(true); } }}>
              <option value="">Cuenta…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{entityName(a)} · {a.name}</option>)}
              <option value="new">＋ Otra cuenta o entidad…</option>
            </select>
            <select name="category">
              <option value="">Categoría…</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <input name="date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required />
            <input name="note" placeholder="Nota" />
            <button>Guardar</button>
          </form>
        )}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <h2>
          Historial{filter && acc(filter) ? ` · ${acc(filter)!.name}` : ""}
          {filter && <button className="link" onClick={() => setFilter(null)}>Ver todas</button>}
        </h2>
        <table>
          <thead><tr><th>Fecha</th><th>Cuenta</th><th>Categoría</th><th>Nota</th><th className="num">Monto</th><th /></tr></thead>
          <tbody>
            {txs.map((t) => {
              const a = acc(t.account_id);
              return (
                <tr key={t.id}>
                  <td>{t.date}</td>
                  <td>
                    <span className="cell-acc">
                      {a && <InstitutionLogo inst={instOf(a)} name={entityName(a)} size={26} />}
                      {a ? `${entityName(a)} · ${a.name}` : "—"}
                    </span>
                  </td>
                  <td>{catName(t.category_id)}</td><td>{t.note}</td>
                  <td className={`num ${t.kind === "income" ? "pos" : "neg"}`}>
                    {t.kind === "income" ? "+" : "−"}{money(t.amount)}
                  </td>
                  <td><button className="link" onClick={() => api.del(`/transactions/${t.id}`).then(load)}>✕</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {txs.length === 0 && <p className="empty">Sin movimientos todavía.</p>}
      </div>

      <AnimatePresence>
        {modal && <AccountModal key="acc" onClose={() => setModal(false)} onCreated={() => { setModal(false); load(); }} />}
      </AnimatePresence>
    </>
  );
}
