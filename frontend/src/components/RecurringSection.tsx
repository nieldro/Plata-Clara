import { FormEvent, useCallback, useEffect, useState } from "react";
import { Account, api, Category, loadInstitutions, localDate, money } from "../api";

type Rec = {
  id: number; account_id: number; category_id: number | null; kind: "income" | "expense";
  amount: number; note: string; frequency: "weekly" | "biweekly" | "monthly"; next_date: string; active: boolean;
};

const FREQ = { weekly: "Cada semana", biweekly: "Cada 15 días", monthly: "Cada mes" };

export default function RecurringSection() {
  const [recs, setRecs] = useState<Rec[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => setRecs(await api.get("/recurring")), []);
  useEffect(() => {
    load();
    api.get<Account[]>("/accounts").then(setAccounts);
    api.get<Category[]>("/categories").then(setCats);
    loadInstitutions();
  }, [load]);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/recurring", {
        account_id: Number(f.get("account")),
        category_id: f.get("category") ? Number(f.get("category")) : null,
        kind: f.get("kind"), amount: Number(f.get("amount")), note: f.get("note") ?? "",
        frequency: f.get("frequency"), start_date: f.get("start"),
      });
      await api.post("/recurring/run");
      form.reset();
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const accName = (id: number) => accounts.find((a) => a.id === id)?.name ?? "—";
  const catName = (id: number | null) => cats.find((c) => c.id === id)?.name ?? "—";

  return (
    <div className="card">
      <h2>Pagos e ingresos recurrentes</h2>
      <p className="empty">Arriendo, suscripciones, nómina… Se registran solos cuando llega la fecha (y si estuviste días sin entrar, se ponen al día).</p>
      <form className="row" onSubmit={add}>
        <select name="kind"><option value="expense">Gasto</option><option value="income">Ingreso</option></select>
        <input name="amount" type="number" min="1" step="0.01" placeholder="Monto" required />
        <select name="account" required>
          <option value="">Cuenta…</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select name="category">
          <option value="">Categoría…</option>
          {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select name="frequency" defaultValue="monthly">
          {Object.entries(FREQ).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input name="start" type="date" defaultValue={localDate()} required title="Primera vez" />
        <input name="note" placeholder="Descripción (ej. Arriendo)" />
        <button>Crear</button>
      </form>
      {error && <p className="error">{error}</p>}

      {recs.length > 0 && (
        <table>
          <thead><tr><th>Descripción</th><th>Cuenta</th><th>Frecuencia</th><th>Próxima</th><th className="num">Monto</th><th /></tr></thead>
          <tbody>
            {recs.map((r) => (
              <tr key={r.id} style={{ opacity: r.active ? 1 : 0.5 }}>
                <td>{r.note || catName(r.category_id)}</td>
                <td>{accName(r.account_id)}</td>
                <td>{FREQ[r.frequency]}</td>
                <td>{r.next_date}</td>
                <td className={`num ${r.kind === "income" ? "pos" : "neg"}`}>{r.kind === "income" ? "+" : "−"}{money(r.amount)}</td>
                <td>
                  <button className="link" onClick={() => api.post(`/recurring/${r.id}/toggle`).then(load)}>{r.active ? "Pausar" : "Activar"}</button>
                  <button className="link" aria-label="Eliminar recurrente"
                    onClick={() => confirm("¿Eliminar este movimiento recurrente? Los que ya se registraron se conservan.") && api.del(`/recurring/${r.id}`).then(load)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
