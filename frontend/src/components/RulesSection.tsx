import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, Category } from "../api";

type Rule = { id: number; keyword: string; category_id: number; category: string; hits: number; manual: boolean };

export default function RulesSection({ cats }: { cats: Category[] }) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [error, setError] = useState("");
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => setRules(await api.get("/rules")), []);
  useEffect(() => { load(); }, [load]);

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api.post("/rules", { keyword: String(f.get("keyword")), category_id: Number(f.get("category")) });
      form.reset();
      setError("");
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const shown = showAll ? rules : rules.slice(0, 8);

  return (
    <div className="card">
      <h2>Categorización automática</h2>
      <p className="empty">
        Plata Clara aprende de lo que categorizas: si pones «Éxito» en Mercado, la próxima vez lo sugiere sola.
        Aquí puedes forzar una palabra a una categoría; esas reglas mandan sobre lo aprendido.
      </p>
      <form className="row" onSubmit={add}>
        <input name="keyword" placeholder="Palabra (ej. netflix)" required maxLength={60} />
        <select name="category" required defaultValue="">
          <option value="">Categoría…</option>
          {cats.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.kind === "income" ? "ingreso" : "gasto"})</option>)}
        </select>
        <button>Crear regla</button>
      </form>
      {error && <p className="error">{error}</p>}
      {rules.length > 0 && (
        <>
          <table>
            <thead><tr><th>Palabra</th><th>Categoría</th><th>Origen</th><th /></tr></thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  <td>{r.keyword}</td>
                  <td>{r.category}</td>
                  <td>{r.manual ? "Manual" : `Aprendida · ${r.hits} ${r.hits === 1 ? "vez" : "veces"}`}</td>
                  <td className="actions"><button className="link" aria-label={`Borrar la regla «${r.keyword}»`} onClick={() => api.del(`/rules/${r.id}`).then(load)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rules.length > 8 && (
            <button className="link" onClick={() => setShowAll(!showAll)}>{showAll ? "Ver menos" : `Ver las ${rules.length} reglas`}</button>
          )}
        </>
      )}
    </div>
  );
}
