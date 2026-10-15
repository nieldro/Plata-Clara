import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Account, api, Category, money } from "../api";
import CountUp from "../components/CountUp";

type Payment = { id: number; amount: number; date: string; note: string; in_account: boolean };
type Loan = {
  id: number; person: string; direction: "lent" | "borrowed"; amount: number; paid: number; outstanding: number;
  settled: boolean; date: string; due_date: string | null; note: string; overdue: boolean; payments?: Payment[];
};
type Summary = { owed_to_me: number; i_owe: number; net: number; overdue: number; people: { person: string; net: number }[] };
type Row = { person: string; amount: string };

const today = () => new Date().toISOString().slice(0, 10);

export default function Loans() {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [status, setStatus] = useState<"open" | "settled">("open");
  const [open, setOpen] = useState<number | null>(null);
  const [detail, setDetail] = useState<Loan | null>(null);
  const [error, setError] = useState("");

  const [rows, setRows] = useState<Row[]>([{ person: "", amount: "" }]);
  const [custom, setCustom] = useState(false);
  const [total, setTotal] = useState("");

  const load = useCallback(async () => {
    setLoans(await api.get(`/loans?status=${status}`));
    setSummary(await api.get("/loans/summary"));
  }, [status]);
  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);
  useEffect(() => {
    api.get<Account[]>("/accounts").then(setAccounts);
    api.get<Category[]>("/categories").then(setCats);
  }, []);

  const fail = (e: unknown) => setError((e as Error).message);

  async function openLoan(id: number) {
    if (open === id) return setOpen(null);
    setOpen(id);
    setDetail(await api.get<Loan>(`/loans/${id}`));
  }
  const refreshDetail = async (id: number) => { setDetail(await api.get<Loan>(`/loans/${id}`)); await load(); };

  async function addLoan(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/loans", {
        person: f.get("person"), direction: f.get("direction"), amount: Number(f.get("amount")), date: f.get("date"),
        due_date: f.get("due") || null, note: f.get("note") ?? "", account_id: f.get("account") ? Number(f.get("account")) : null,
      });
      form.reset();
      setError("");
      load();
    } catch (err) { fail(err); }
  }

  async function addPayment(e: FormEvent<HTMLFormElement>, loan: Loan) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post(`/loans/${loan.id}/payments`, {
        amount: Number(f.get("amount")), date: f.get("date"), note: f.get("note") ?? "",
        account_id: f.get("account") ? Number(f.get("account")) : null,
      });
      form.reset();
      setError("");
      await refreshDetail(loan.id);
    } catch (err) { fail(err); }
  }

  async function removePayment(loan: Loan, p: Payment) {
    if (!confirm("¿Borrar este abono? Si movió dinero en una cuenta, se revierte.")) return;
    await api.del(`/loans/${loan.id}/payments/${p.id}`);
    await refreshDetail(loan.id);
  }
  async function removeLoan(loan: Loan) {
    if (!confirm(`¿Borrar el préstamo con ${loan.person}? Se revierte lo que haya movido en tus cuentas.`)) return;
    await api.del(`/loans/${loan.id}`);
    setOpen(null);
    load();
  }

  // ---- gasto compartido
  const people = rows.filter((r) => r.person.trim());
  const totalNum = Number(total) || 0;
  const preview = useMemo(() => {
    if (!totalNum || people.length === 0) return null;
    if (custom) {
      const given = people.reduce((a, r) => a + (Number(r.amount) || 0), 0);
      return { each: null as number | null, mine: totalNum - given };
    }
    const each = Math.floor((totalNum / (people.length + 1)) * 100) / 100;
    return { each, mine: Math.round((totalNum - each * people.length) * 100) / 100 };
  }, [totalNum, people, custom]);

  async function split(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/splits", {
        account_id: Number(f.get("account")), category_id: f.get("category") ? Number(f.get("category")) : null,
        total: totalNum, date: f.get("date"), note: f.get("note") ?? "", due_date: f.get("due") || null,
        participants: people.map((r) => ({ person: r.person.trim(), amount: custom ? Number(r.amount) : null })),
      });
      form.reset();
      setRows([{ person: "", amount: "" }]);
      setTotal("");
      setError("");
      load();
    } catch (err) { fail(err); }
  }

  const setRow = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <>
      {summary && (
        <div className="tiles">
          <div className="card tile"><small>Te deben</small><b className="pos"><CountUp value={Number(summary.owed_to_me)} format={(n) => money(n)} /></b></div>
          <div className="card tile"><small>Debes</small><b className="neg"><CountUp value={Number(summary.i_owe)} format={(n) => money(n)} /></b></div>
          <div className="card tile"><small>Saldo neto</small><b className={Number(summary.net) < 0 ? "neg" : ""}><CountUp value={Number(summary.net)} format={(n) => money(n)} /></b></div>
          {summary.overdue > 0 && <div className="card tile"><small>Vencidos</small><b className="neg">{summary.overdue}</b></div>}
        </div>
      )}
      {error && <p className="error">{error}</p>}

      {summary && summary.people.length > 0 && (
        <div className="card">
          <h2>Por persona</h2>
          <table><tbody>
            {summary.people.map((p) => (
              <tr key={p.person}>
                <td>{p.person}</td>
                <td className={`num ${Number(p.net) > 0 ? "pos" : "neg"}`}>
                  {Number(p.net) > 0 ? `te debe ${money(p.net)}` : `le debes ${money(-Number(p.net))}`}
                </td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}

      <div className="card">
        <h2>Dividir una cuenta</h2>
        <p className="empty">Pagaste una cuenta entre varios: solo tu parte cuenta como gasto (y entra a tu presupuesto); lo de los demás queda como «te deben».</p>
        <form onSubmit={split}>
          <div className="row">
            <input name="note" placeholder="¿Qué fue? (ej. Cena del viernes)" required />
            <input type="number" min="1" step="0.01" placeholder="Total de la cuenta" value={total} onChange={(e) => setTotal(e.target.value)} required />
            <select name="account" required defaultValue="">
              <option value="">¿Con qué cuenta pagaste?</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <select name="category" defaultValue="">
              <option value="">Categoría de tu parte…</option>
              {cats.filter((c) => c.kind === "expense").map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <input name="date" type="date" defaultValue={today()} required />
            <input name="due" type="date" title="Fecha límite para que te paguen (opcional)" />
          </div>

          <p className="empty" style={{ marginBottom: 4 }}>¿Con quién la compartiste?</p>
          {rows.map((r, i) => (
            <div className="row" key={i} style={{ marginTop: 6 }}>
              <input placeholder={`Persona ${i + 1}`} value={r.person} onChange={(e) => setRow(i, { person: e.target.value })} maxLength={100} />
              {custom && <input type="number" min="0.01" step="0.01" placeholder="Su parte" value={r.amount} onChange={(e) => setRow(i, { amount: e.target.value })} />}
              {rows.length > 1 && <button type="button" className="link" onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button>}
            </div>
          ))}
          <div className="row">
            <button type="button" className="btn-ghost" onClick={() => rows.length < 20 && setRows([...rows, { person: "", amount: "" }])}>＋ Otra persona</button>
            <label className="check"><input type="checkbox" checked={custom} onChange={(e) => setCustom(e.target.checked)} /> Montos distintos (si no, partes iguales)</label>
          </div>

          {preview && (
            <p className="hint">
              {preview.mine < 0
                ? "⚠️ Lo que les cobras supera el total de la cuenta."
                : <>Tu parte: <b>{money(preview.mine)}</b>{preview.each !== null && <> · cada uno te debe <b>{money(preview.each)}</b></>}</>}
            </p>
          )}
          <div className="row modal-actions"><button disabled={!preview || preview.mine < 0}>Registrar cuenta dividida</button></div>
        </form>
      </div>

      <div className="card">
        <h2>Nuevo préstamo</h2>
        <form className="row" onSubmit={addLoan}>
          <select name="direction"><option value="lent">Le presté a alguien</option><option value="borrowed">Alguien me prestó</option></select>
          <input name="person" placeholder="Persona" required maxLength={100} />
          <input name="amount" type="number" min="1" step="0.01" placeholder="Monto" required />
          <input name="date" type="date" defaultValue={today()} required />
          <input name="due" type="date" title="Fecha límite (opcional)" />
          <select name="account" defaultValue="" title="Si eliges una cuenta, el dinero entra o sale de ella">
            <option value="">Solo anotar (sin mover cuentas)</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>Mover dinero en {a.name}</option>)}
          </select>
          <input name="note" placeholder="Nota (opcional)" />
          <button>Guardar</button>
        </form>
      </div>

      <div className="card">
        <h2>
          Préstamos {status === "open" ? "abiertos" : "saldados"}
          <button className="link" onClick={() => setStatus(status === "open" ? "settled" : "open")}>
            Ver {status === "open" ? "saldados" : "abiertos"}
          </button>
        </h2>
        {loans.length === 0 && <p className="empty">{status === "open" ? "Nadie te debe y no debes nada. 🎉" : "Aún no hay préstamos saldados."}</p>}
        {loans.map((l) => (
          <div className="loan" key={l.id}>
            <div className="loan-head" onClick={() => openLoan(l.id)}>
              <div>
                <b>{l.person}</b> {l.overdue && <span className="badge-state bad">Vencido</span>}
                <small className="block">{l.direction === "lent" ? "Te debe" : "Le debes"} · {l.date}{l.due_date ? ` · límite ${l.due_date}` : ""}{l.note ? ` · ${l.note}` : ""}</small>
              </div>
              <div className="num">
                <b className={l.direction === "lent" ? "pos" : "neg"}>{money(l.outstanding)}</b>
                <small className="block">de {money(l.amount)}</small>
              </div>
            </div>
            {open === l.id && detail && detail.id === l.id && (
              <div className="loan-body">
                {detail.payments && detail.payments.length > 0 && (
                  <table><tbody>
                    {detail.payments.map((p) => (
                      <tr key={p.id}>
                        <td>{p.date}</td><td>{p.note || "Abono"}{p.in_account && " · en cuenta"}</td>
                        <td className="num">{money(p.amount)}</td>
                        <td className="actions"><button className="link" onClick={() => removePayment(detail, p)}>✕</button></td>
                      </tr>
                    ))}
                  </tbody></table>
                )}
                {!detail.settled && (
                  <form className="row" onSubmit={(e) => addPayment(e, detail)}>
                    <input name="amount" type="number" min="0.01" step="0.01" max={detail.outstanding} placeholder={detail.direction === "lent" ? "Monto que te pagó" : "Monto que pagas"} required />
                    <input name="date" type="date" defaultValue={today()} required />
                    <select name="account" defaultValue="">
                      <option value="">Solo anotar</option>
                      {accounts.map((a) => <option key={a.id} value={a.id}>{detail.direction === "lent" ? "Entró a" : "Salió de"} {a.name}</option>)}
                    </select>
                    <input name="note" placeholder="Nota" />
                    <button>Registrar abono</button>
                  </form>
                )}
                <button className="link" onClick={() => removeLoan(detail)}>Borrar préstamo</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
