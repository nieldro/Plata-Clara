import { AnimatePresence } from "framer-motion";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ACCOUNT_TYPES, Account, api, Category, Institution, loadInstitutions, money, Tx } from "../api";
import AccountModal from "../components/AccountModal";
import EditTransactionModal from "../components/EditTransactionModal";
import TransactionHistory from "../components/TransactionHistory";
import InstitutionLogo from "../components/InstitutionLogo";

export default function Transactions() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [insts, setInsts] = useState<Institution[]>([]);
  const [filter, setFilter] = useState<number | null>(null);
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Tx | null>(null);
  const [error, setError] = useState("");

  const [version, setVersion] = useState(0); // al cambiar, el historial se vuelve a pedir

  const load = useCallback(async () => {
    setAccounts(await api.get("/accounts"));
    setVersion((v) => v + 1);
  }, []);
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

  async function addTransfer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/transfers", {
        from_account_id: Number(f.get("from")), to_account_id: Number(f.get("to")),
        amount: Number(f.get("amount")), date: f.get("date"), note: f.get("note") ?? "",
      });
      form.reset();
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function addCategory(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/categories", { name: String(f.get("name")).trim(), kind: f.get("kind") });
      form.reset();
      setCats(await api.get("/categories"));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeCategory(c: Category) {
    if (!confirm(`¿Borrar la categoría «${c.name}»? Sus movimientos quedarán sin categoría.`)) return;
    await api.del(`/categories/${c.id}`);
    setCats(await api.get("/categories"));
    load();
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

      {accounts.length >= 2 && (
        <div className="card">
          <h2>Transferir entre mis cuentas</h2>
          <p className="empty">Útil para pagar una tarjeta desde tu banco o mover plata a tu billetera. No cuenta como gasto ni ingreso.</p>
          <form className="row" onSubmit={addTransfer}>
            <select name="from" required defaultValue="">
              <option value="">Desde…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{entityName(a)} · {a.name}</option>)}
            </select>
            <select name="to" required defaultValue="">
              <option value="">Hacia…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{entityName(a)} · {a.name}</option>)}
            </select>
            <input name="amount" type="number" step="0.01" min="0.01" placeholder="Monto" required />
            <input name="date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required />
            <input name="note" placeholder="Nota (opcional)" />
            <button>Transferir</button>
          </form>
        </div>
      )}

      <div className="card">
        <h2>Mis categorías</h2>
        <div className="chips">
          {cats.map((c) => (
            <span key={c.id} className={`chip ${c.kind}`}>
              {c.name}
              <button className="link" title="Borrar" onClick={() => removeCategory(c)}>✕</button>
            </span>
          ))}
        </div>
        <form className="row" onSubmit={addCategory}>
          <input name="name" placeholder="Nueva categoría (ej. Mascotas)" required maxLength={100} />
          <select name="kind"><option value="expense">De gasto</option><option value="income">De ingreso</option></select>
          <button>Agregar</button>
        </form>
      </div>

      <TransactionHistory
        accounts={accounts} cats={cats} insts={insts} accountFilter={filter} version={version}
        onEdit={setEditing} onChanged={load} onClearAccount={() => setFilter(null)}
      />

      <AnimatePresence>
        {editing && (
          <EditTransactionModal key="edit" tx={editing} accounts={accounts} cats={cats}
            onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
        )}
        {modal && <AccountModal key="acc" onClose={() => setModal(false)} onCreated={() => { setModal(false); load(); }} />}
      </AnimatePresence>
    </>
  );
}
