import { useCallback, useEffect, useRef, useState } from "react";
import { Account, api, Category, download, getPage, Institution, money, Tx } from "../api";
import InstitutionLogo from "./InstitutionLogo";

const PAGE = 50;

type Filters = {
  q: string; date_from: string; date_to: string; min_amount: string; max_amount: string;
  category: string; kind: string; account: string; tag: string;
};
const EMPTY: Filters = { q: "", date_from: "", date_to: "", min_amount: "", max_amount: "", category: "", kind: "", account: "", tag: "" };

type Props = {
  accounts: Account[];
  cats: Category[];
  tagNames: string[];
  insts: Institution[];
  accountFilter: number | null;
  version: number;
  onEdit: (t: Tx) => void;
  onReceipts: (t: Tx) => void;
  onChanged: () => void;
  onClearAccount: () => void;
};

function toQuery(f: Filters, accountFilter: number | null, offset: number, paged = true) {
  const p = new URLSearchParams(paged ? { limit: String(PAGE), offset: String(offset) } : {});
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.date_from) p.set("date_from", f.date_from);
  if (f.date_to) p.set("date_to", f.date_to);
  if (f.min_amount) p.set("min_amount", f.min_amount);
  if (f.max_amount) p.set("max_amount", f.max_amount);
  if (f.category === "none") p.set("uncategorized", "true");
  else if (f.category) p.set("category_id", f.category);
  if (f.kind) p.set("kind", f.kind);
  if (f.tag) p.set("tag", f.tag);
  const account = f.account || (accountFilter ? String(accountFilter) : "");
  if (account) p.set("account_id", account);
  return p.toString();
}

export default function TransactionHistory({ accounts, cats, tagNames, insts, accountFilter, version, onEdit, onReceipts, onChanged, onClearAccount }: Props) {
  const [f, setF] = useState<Filters>(EMPTY);
  const [debouncedQ, setDebouncedQ] = useState("");
  const [items, setItems] = useState<Tx[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const reqId = useRef(0);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(f.q), 300);
    return () => clearTimeout(t);
  }, [f.q]);

  const effective = { ...f, q: debouncedQ };
  const key = JSON.stringify([effective, accountFilter, version]);

  const fetchPage = useCallback(async (offset: number) => {
    const id = ++reqId.current; // descarta respuestas viejas si llegan tarde
    setLoading(true);
    try {
      const r = await getPage<Tx>(`/transactions?${toQuery(effective, accountFilter, offset)}`);
      if (id !== reqId.current) return;
      setItems((prev) => (offset === 0 ? r.items : [...prev, ...r.items]));
      setTotal(r.total);
      setError("");
    } catch (err) {
      if (id === reqId.current) setError((err as Error).message);
    } finally {
      if (id === reqId.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => { fetchPage(0); }, [fetchPage]);

  const set = (k: keyof Filters) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));
  const active = Object.entries(f).some(([, v]) => v !== "");
  const instOf = (a: Account) => insts.find((i) => i.slug === a.institution);
  const entityName = (a: Account) => instOf(a)?.name ?? a.institution_name ?? "Efectivo";
  const acc = (id: number) => accounts.find((a) => a.id === id);
  const catName = (id: number | null) => cats.find((c) => c.id === id)?.name ?? "—";

  const [exporting, setExporting] = useState(false);
  async function exportAs(format: "csv" | "xlsx") {
    setExporting(true);
    try {
      // exporta lo que estás viendo: los mismos filtros, sin paginar
      await download(`/export/transactions?format=${format}&${toQuery(effective, accountFilter, 0, false)}`);
      setError("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setExporting(false);
    }
  }

  const sum = (kind: "income" | "expense") =>
    items.filter((t) => !t.transfer_id && t.kind === kind).reduce((a, t) => a + Number(t.amount), 0);

  return (
    <div className="card">
      <h2>
        Historial{accountFilter && acc(accountFilter) ? ` · ${acc(accountFilter)!.name}` : ""}
        {accountFilter && <button className="link" onClick={onClearAccount}>Ver todas las cuentas</button>}
      </h2>

      <div className="filters">
        <input className="grow" type="search" placeholder="Buscar por nota o categoría…" value={f.q} onChange={set("q")} />
        <select value={f.kind} onChange={set("kind")}>
          <option value="">Gastos e ingresos</option>
          <option value="expense">Solo gastos</option>
          <option value="income">Solo ingresos</option>
        </select>
        <select value={f.category} onChange={set("category")}>
          <option value="">Todas las categorías</option>
          <option value="none">Sin categoría</option>
          {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {tagNames.length > 0 && (
          <select value={f.tag} onChange={set("tag")}>
            <option value="">Todas las etiquetas</option>
            {tagNames.map((t) => <option key={t} value={t}>#{t}</option>)}
          </select>
        )}
        {!accountFilter && (
          <select value={f.account} onChange={set("account")}>
            <option value="">Todas las cuentas</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        )}
        <input type="date" title="Desde" value={f.date_from} onChange={set("date_from")} />
        <input type="date" title="Hasta" value={f.date_to} onChange={set("date_to")} />
        <input type="number" min="0" placeholder="Monto mín." value={f.min_amount} onChange={set("min_amount")} />
        <input type="number" min="0" placeholder="Monto máx." value={f.max_amount} onChange={set("max_amount")} />
        {active && <button className="link" onClick={() => setF(EMPTY)}>Limpiar filtros</button>}
        <span className="export-btns">
          <button className="btn-ghost" disabled={exporting || total === 0} onClick={() => exportAs("xlsx")}
            title="Descarga lo que ves ahora (con los filtros aplicados)">⬇ Excel</button>
          <button className="btn-ghost" disabled={exporting || total === 0} onClick={() => exportAs("csv")}>⬇ CSV</button>
        </span>
      </div>

      <p className="summary-line">
        {total} {total === 1 ? "movimiento" : "movimientos"}
        {items.length > 0 && (
          <> · mostrando ingresos <b className="pos">{money(sum("income"))}</b> y gastos <b className="neg">{money(sum("expense"))}</b></>
        )}
      </p>
      {error && <p className="error">{error}</p>}

      <div className="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Cuenta</th><th>Categoría</th><th>Nota</th><th className="num">Monto</th><th /></tr></thead>
          <tbody>
            {items.map((t) => {
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
                  <td>{t.transfer_id ? "↔ Transferencia" : t.loan_id ? "🤝 Préstamo" : catName(t.category_id)}</td>
                  <td>
                    {t.note}
                    {t.tags.map((g) => <span className="tagchip mini" key={g}>#{g}</span>)}
                  </td>
                  <td className={`num ${t.kind === "income" ? "pos" : "neg"}`}>{t.kind === "income" ? "+" : "−"}{money(t.amount)}</td>
                  <td className="actions">
                    {!t.transfer_id && (
                      <button className={`link ${t.attachments ? "has-files" : ""}`} title="Recibos" onClick={() => onReceipts(t)}>
                        📎{t.attachments > 0 && <sup>{t.attachments}</sup>}
                      </button>
                    )}
                    {!t.transfer_id && !t.loan_id && <button className="link" title="Editar" onClick={() => onEdit(t)}>✎</button>}
                    {t.loan_id
                      ? <small title="Se gestiona desde «Quién me debe»">en Préstamos</small>
                      : <button className="link" title="Borrar" onClick={() => api.del(`/transactions/${t.id}`).then(onChanged)}>✕</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!loading && items.length === 0 && (
        <p className="empty">{active ? "Ningún movimiento coincide con esos filtros." : "Sin movimientos todavía."}</p>
      )}
      {items.length < total && (
        <div className="row modal-actions">
          <button className="btn-ghost" disabled={loading} onClick={() => fetchPage(items.length)}>
            {loading ? "Cargando…" : `Cargar más (${total - items.length} restantes)`}
          </button>
        </div>
      )}
    </div>
  );
}
