import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { Account, api, Category, loadInstitutions, money, splitTags } from "../api";
import TagInput from "../components/TagInput";

type Row = {
  line: number; date: string | null; description: string; amount: number | null; kind: "income" | "expense" | null;
  error: string | null; import_hash: string | null; duplicate: "exact" | "possible" | null; category_id: number | null;
};
type Mapping = { date: number | null; description: number | null; amount: number | null; debit: number | null; credit: number | null };
type Stats = {
  total: number; valid: number; errors: number; exact_duplicates: number; possible_duplicates: number;
  new_income: number; new_expense: number; from: string | null; to: string | null;
};
type Preview = { columns: string[]; header_row: number | null; mapping: Mapping; sample: string[][]; needs_mapping: boolean; rows: Row[]; stats: Stats | null };

const FIELDS: { key: keyof Mapping; label: string }[] = [
  { key: "date", label: "Fecha" }, { key: "description", label: "Descripción" }, { key: "amount", label: "Monto (una sola columna)" },
  { key: "debit", label: "Débito / retiros" }, { key: "credit", label: "Crédito / abonos" },
];
const ACCEPT = ".csv,.txt,.tsv,.xlsx";

export default function Import() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [accountId, setAccountId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dateOrder, setDateOrder] = useState<"dmy" | "mdy">("dmy");
  const [invert, setInvert] = useState(false);
  const [hasHeader, setHasHeader] = useState(false);
  const [mapping, setMapping] = useState<Record<keyof Mapping, string>>({ date: "", description: "", amount: "", debit: "", credit: "" });
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cat, setCat] = useState<Record<string, string>>({});
  const [tags, setTags] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ created: number; skipped: number } | null>(null);
  const [drag, setDrag] = useState(false);

  useEffect(() => {
    api.get<Account[]>("/accounts").then(setAccounts);
    api.get<Category[]>("/categories").then(setCats);
    loadInstitutions();
  }, []);

  const account = accounts.find((a) => String(a.id) === accountId);
  useEffect(() => { setInvert(account?.type === "credit_card"); }, [account?.type]); // en tarjetas las compras vienen positivas

  async function run(useMapping: boolean) {
    if (!file || !accountId) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("account_id", accountId);
      form.append("date_order", dateOrder);
      form.append("invert", String(invert));
      if (useMapping) {
        form.append("has_header", String(hasHeader));
        for (const [k, v] of Object.entries(mapping)) form.append(`${k}_col`, v === "" ? "-1" : v);
      }
      const p = await api.upload<Preview>("/imports/preview", form);
      setPreview(p);
      if (p.needs_mapping) {
        setMapping({ date: "", description: "", amount: "", debit: "", credit: "" });
      } else {
        setMapping(Object.fromEntries(Object.entries(p.mapping).map(([k, v]) => [k, v === null ? "" : String(v)])) as Record<keyof Mapping, string>);
        setSelected(new Set(p.rows.filter((r) => !r.error && !r.duplicate).map((r) => r.import_hash!)));
        setCat(Object.fromEntries(p.rows.filter((r) => r.category_id).map((r) => [r.import_hash!, String(r.category_id)])));
      }
    } catch (err) {
      setPreview(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function pickFile(f: File | undefined) {
    if (!f) return;
    setFile(f);
    setPreview(null);
    setResult(null);
    setError("");
  }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); pickFile(e.dataTransfer.files[0]); };

  const chosen = useMemo(() => preview?.rows.filter((r) => r.import_hash && selected.has(r.import_hash)) ?? [], [preview, selected]);
  const totals = useMemo(() => ({
    income: chosen.filter((r) => r.kind === "income").reduce((a, r) => a + Number(r.amount), 0),
    expense: chosen.filter((r) => r.kind === "expense").reduce((a, r) => a + Number(r.amount), 0),
  }), [chosen]);

  function toggle(hash: string) {
    setSelected((s) => { const n = new Set(s); n.has(hash) ? n.delete(hash) : n.add(hash); return n; });
  }
  const selectable = preview?.rows.filter((r) => !r.error && r.import_hash) ?? [];

  async function commit() {
    if (!preview || chosen.length === 0) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.post<{ created: number; skipped: number }>("/imports/commit", {
        account_id: Number(accountId),
        rows: chosen.map((x) => ({
          date: x.date, description: x.description, amount: x.amount, kind: x.kind,
          category_id: cat[x.import_hash!] ? Number(cat[x.import_hash!]) : null, import_hash: x.import_hash, tags,
        })),
      });
      setResult(r);
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const badge = (r: Row) =>
    r.error ? <span className="badge-state bad" title={r.error}>Error</span>
      : r.duplicate === "exact" ? <span className="badge-state dup" title="Ya lo importaste antes">Ya importado</span>
        : r.duplicate === "possible" ? <span className="badge-state maybe" title="Hay un movimiento tuyo con la misma fecha y monto">Posible duplicado</span>
          : null;

  return (
    <>
      <div className="card">
        <h2>1 · Elige la cuenta y el archivo</h2>
        <p className="empty">Descarga el extracto desde la página de tu banco (CSV o Excel) y súbelo aquí. Verás todo antes de guardar nada.</p>
        <div className="row">
          <select value={accountId} onChange={(e: ChangeEvent<HTMLSelectElement>) => { setAccountId(e.target.value); setPreview(null); }}>
            <option value="">¿A qué cuenta pertenece?</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select value={dateOrder} onChange={(e) => setDateOrder(e.target.value as "dmy" | "mdy")} title="Orden de las fechas del archivo">
            <option value="dmy">Fechas día/mes/año</option>
            <option value="mdy">Fechas mes/día/año</option>
          </select>
        </div>
        <label className={`dropzone ${drag ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)} onDrop={onDrop}>
          <input type="file" accept={ACCEPT} onChange={(e) => pickFile(e.target.files?.[0])} hidden />
          {file ? <><b>{file.name}</b><small>{(file.size / 1024).toFixed(0)} KB · clic para cambiar</small></>
            : <><b>Arrastra el extracto aquí</b><small>o haz clic para elegirlo · CSV, TXT o Excel (.xlsx) · máx. 5 MB</small></>}
        </label>
        {account?.type === "credit_card" && (
          <label className="check"><input type="checkbox" checked={invert} onChange={(e) => setInvert(e.target.checked)} />
            Las compras aparecen con monto positivo (típico en tarjetas de crédito)</label>
        )}
        <div className="row modal-actions">
          <button disabled={!file || !accountId || busy} onClick={() => run(false)}>{busy ? "Leyendo…" : "Ver vista previa"}</button>
        </div>
        {error && <p className="error">{error}</p>}
        {result && (
          <p className="ok-msg">
            ✓ Se importaron <b>{result.created}</b> movimientos{result.skipped > 0 && <> ({result.skipped} ya existían y se omitieron)</>}.
            Las categorías que elegiste quedan aprendidas para la próxima vez.
          </p>
        )}
      </div>

      {preview?.needs_mapping && (
        <div className="card">
          <h2>2 · No reconocí las columnas</h2>
          <p className="empty">Dime cuál columna es cuál. Si el archivo tiene dos columnas de monto (débito y crédito) usa esas en lugar de «Monto».</p>
          <div className="table-wrap">
            <table>
              <thead><tr>{preview.columns.map((c, i) => <th key={i}>{c}</th>)}</tr></thead>
              <tbody>{preview.sample.map((r, i) => <tr key={i}>{preview.columns.map((_, j) => <td key={j}>{r[j] ?? ""}</td>)}</tr>)}</tbody>
            </table>
          </div>
          <form className="row" onSubmit={(e: FormEvent) => { e.preventDefault(); run(true); }}>
            {FIELDS.map((f) => (
              <label key={f.key}>{f.label}
                <select value={mapping[f.key]} onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value })}>
                  <option value="">—</option>
                  {preview.columns.map((c, i) => <option key={i} value={i}>{c}</option>)}
                </select>
              </label>
            ))}
            <label className="check"><input type="checkbox" checked={hasHeader} onChange={(e) => setHasHeader(e.target.checked)} /> La primera fila es de encabezados</label>
            <button disabled={busy}>Aplicar columnas</button>
          </form>
        </div>
      )}

      {preview && !preview.needs_mapping && preview.stats && (
        <div className="card">
          <h2>2 · Revisa antes de importar</h2>
          <div className="facts">
            <div><small>Período</small><b>{preview.stats.from} → {preview.stats.to}</b></div>
            <div><small>Filas leídas</small><b>{preview.stats.total}</b></div>
            <div><small>Ya importadas</small><b>{preview.stats.exact_duplicates}</b></div>
            <div><small>Posibles duplicados</small><b>{preview.stats.possible_duplicates}</b></div>
            <div><small>Con error</small><b className={preview.stats.errors ? "neg" : ""}>{preview.stats.errors}</b></div>
          </div>

          <details className="cols">
            <summary>Columnas detectadas — ¿algo mal? Corrígelo</summary>
            <form className="row" onSubmit={(e: FormEvent) => { e.preventDefault(); run(true); }}>
              {FIELDS.map((f) => (
                <label key={f.key}>{f.label}
                  <select value={mapping[f.key]} onChange={(e) => setMapping({ ...mapping, [f.key]: e.target.value })}>
                    <option value="">—</option>
                    {preview.columns.map((c, i) => <option key={i} value={i}>{c}</option>)}
                  </select>
                </label>
              ))}
              <label className="check"><input type="checkbox" checked={invert} onChange={(e) => setInvert(e.target.checked)} /> Invertir ingresos/gastos</label>
              <button disabled={busy}>Releer</button>
            </form>
          </details>

          <div className="row">
            <button className="link" onClick={() => setSelected(new Set(selectable.filter((r) => !r.duplicate).map((r) => r.import_hash!)))}>Solo nuevos</button>
            <button className="link" onClick={() => setSelected(new Set(selectable.map((r) => r.import_hash!)))}>Todos</button>
            <button className="link" onClick={() => setSelected(new Set())}>Ninguno</button>
          </div>

          <div className="table-wrap tall" data-lenis-prevent>
            <table>
              <thead><tr><th /><th>Fecha</th><th>Descripción</th><th>Categoría</th><th className="num">Monto</th><th /></tr></thead>
              <tbody>
                {preview.rows.map((r) => (
                  <tr key={r.line} className={r.error ? "row-bad" : selected.has(r.import_hash ?? "") ? "" : "row-off"}>
                    <td>{!r.error && <input type="checkbox" checked={selected.has(r.import_hash!)} onChange={() => toggle(r.import_hash!)} />}</td>
                    <td>{r.date ?? "—"}</td>
                    <td>{r.description || <i>(sin descripción)</i>}{r.error && <div className="error small">{r.error}</div>}</td>
                    <td>
                      {!r.error && (
                        <select value={cat[r.import_hash!] ?? ""} onChange={(e) => setCat({ ...cat, [r.import_hash!]: e.target.value })}>
                          <option value="">Sin categoría</option>
                          {cats.filter((c) => c.kind === r.kind).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      )}
                    </td>
                    <td className={`num ${r.kind === "income" ? "pos" : "neg"}`}>{r.amount !== null && <>{r.kind === "income" ? "+" : "−"}{money(r.amount)}</>}</td>
                    <td>{badge(r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="row">
            <TagInput suggestions={[]} onChange={setTags} name="import-tags" />
          </div>
          <small>Las etiquetas se aplican a todos los movimientos que importes (ej. «extracto-marzo»).</small>

          <div className="import-foot">
            <span>{chosen.length} seleccionados · <b className="pos">+{money(totals.income)}</b> · <b className="neg">−{money(totals.expense)}</b></span>
            <button disabled={busy || chosen.length === 0} onClick={commit}>{busy ? "Importando…" : `Importar ${chosen.length} movimientos`}</button>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      )}
    </>
  );
}

export { splitTags };
