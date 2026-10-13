import { FormEvent, useCallback, useEffect, useState } from "react";
import { Account, api, Category, money, Tx } from "../api";

export default function Transactions() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [txs, setTxs] = useState<Tx[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setAccounts(await api.get("/accounts"));
    setCats(await api.get("/categories"));
    setTxs(await api.get("/transactions"));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function addAccount(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await api.post("/accounts", { name: f.get("name"), type: f.get("type"), initial_balance: Number(f.get("initial") || 0) });
    e.currentTarget.reset();
    load();
  }

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

  const accName = (id: number) => accounts.find((a) => a.id === id)?.name ?? "—";
  const catName = (id: number | null) => cats.find((c) => c.id === id)?.name ?? "—";

  return (
    <>
      <div className="card">
        <h2>Cuentas</h2>
        <table>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td><td>{a.type}</td><td className="num">{money(a.balance)}</td>
                <td><button className="link" onClick={() => api.del(`/accounts/${a.id}`).then(load)}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <form className="row" onSubmit={addAccount}>
          <input name="name" placeholder="Nombre (ej. Bancolombia)" required />
          <select name="type"><option value="bank">Banco</option><option value="cash">Efectivo</option><option value="wallet">Billetera</option></select>
          <input name="initial" type="number" step="0.01" placeholder="Saldo inicial" />
          <button>Agregar cuenta</button>
        </form>
      </div>

      <div className="card">
        <h2>Nuevo movimiento</h2>
        <form className="row" onSubmit={addTx}>
          <select name="kind"><option value="expense">Gasto</option><option value="income">Ingreso</option></select>
          <input name="amount" type="number" step="0.01" min="0.01" placeholder="Monto" required />
          <select name="account" required>
            <option value="">Cuenta…</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select name="category">
            <option value="">Categoría…</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input name="date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required />
          <input name="note" placeholder="Nota" />
          <button>Guardar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <h2>Historial</h2>
        <table>
          <thead><tr><th>Fecha</th><th>Cuenta</th><th>Categoría</th><th>Nota</th><th className="num">Monto</th><th /></tr></thead>
          <tbody>
            {txs.map((t) => (
              <tr key={t.id}>
                <td>{t.date}</td><td>{accName(t.account_id)}</td><td>{catName(t.category_id)}</td><td>{t.note}</td>
                <td className={`num ${t.kind === "income" ? "pos" : "neg"}`}>
                  {t.kind === "income" ? "+" : "−"}{money(t.amount)}
                </td>
                <td><button className="link" onClick={() => api.del(`/transactions/${t.id}`).then(load)}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
