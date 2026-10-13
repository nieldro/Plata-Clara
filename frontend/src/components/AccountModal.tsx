import { motion } from "framer-motion";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ACCOUNT_TYPES, AccountType, api, Institution, loadInstitutions } from "../api";
import { EASE } from "../theme";
import InstitutionLogo from "./InstitutionLogo";

type Choice = { kind: "inst"; slug: string } | { kind: "other" } | { kind: "cash" } | null;

const DEFAULT_TYPE: Record<string, AccountType> = {
  "Bancos": "savings",
  "Billeteras y neobancos": "wallet",
  "Inversión, fondos y pensiones": "investment",
  "Pagos y cripto": "wallet",
};

export default function AccountModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [insts, setInsts] = useState<Institution[]>([]);
  const [query, setQuery] = useState("");
  const [choice, setChoice] = useState<Choice>(null);
  const [type, setType] = useState<AccountType>("savings");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { loadInstitutions().then(setInsts); }, []);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = insts.filter((i) => !q || i.name.toLowerCase().includes(q));
    const map = new Map<string, Institution[]>();
    list.forEach((i) => map.set(i.category, [...(map.get(i.category) ?? []), i]));
    return [...map.entries()];
  }, [insts, query]);

  const selected = choice?.kind === "inst" ? insts.find((i) => i.slug === choice.slug) : undefined;

  function pick(c: Choice, inst?: Institution) {
    setChoice(c);
    if (c?.kind === "cash") setType("cash");
    else if (inst) setType(DEFAULT_TYPE[inst.category] ?? "savings");
    else if (c?.kind === "other" && type === "cash") setType("savings");
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!choice) return setError("Elige una entidad, «Otra entidad» o «Efectivo»");
    const f = new FormData(e.currentTarget);
    const num = (k: string) => (f.get(k) ? Number(f.get(k)) : null);
    const entity = selected?.name ?? String(f.get("other") ?? "").trim();
    const label = ACCOUNT_TYPES[type];
    setBusy(true);
    setError("");
    try {
      await api.post("/accounts", {
        name: String(f.get("name") || "").trim() || (choice.kind === "cash" ? "Efectivo" : `${entity} · ${label}`),
        type,
        institution: choice.kind === "inst" ? choice.slug : null,
        institution_name: choice.kind === "other" ? entity : null,
        initial_balance: num("balance") ?? 0,
        credit_limit: type === "credit_card" ? num("limit") : null,
        rate: type === "credit_card" ? num("rate") ?? 0 : 0,
        rate_type: f.get("rate_type") || "EA",
        monthly_payment: type === "credit_card" ? num("payment") : null,
      });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const isCard = type === "credit_card";
  const types = (Object.keys(ACCOUNT_TYPES) as AccountType[]).filter((t) => (choice?.kind === "cash" ? t === "cash" : t !== "cash"));

  return (
    <motion.div className="modal-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.form className="card modal wide" onSubmit={submit} data-lenis-prevent
        initial={{ opacity: 0, y: 30, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }} transition={{ duration: 0.5, ease: EASE }}>
        <h2>Agregar cuenta</h2>
        <small>1 · ¿En qué entidad está?</small>
        <input placeholder="Buscar banco, billetera o app de inversión…" value={query} onChange={(e) => setQuery(e.target.value)} />

        <div className="inst-scroll" data-lenis-prevent>
          {groups.map(([cat, list]) => (
            <div key={cat}>
              <p className="inst-cat">{cat}</p>
              <div className="inst-grid">
                {list.map((i) => (
                  <button type="button" key={i.slug}
                    className={`inst ${choice?.kind === "inst" && choice.slug === i.slug ? "on" : ""}`}
                    onClick={() => pick({ kind: "inst", slug: i.slug }, i)}>
                    <InstitutionLogo inst={i} size={36} />
                    <span>{i.name}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
          <p className="inst-cat">Si no aparece</p>
          <div className="inst-grid">
            <button type="button" className={`inst ${choice?.kind === "other" ? "on" : ""}`} onClick={() => pick({ kind: "other" })}>
              <InstitutionLogo name="+" size={36} /><span>Otra entidad o app</span>
            </button>
            <button type="button" className={`inst ${choice?.kind === "cash" ? "on" : ""}`} onClick={() => pick({ kind: "cash" })}>
              <InstitutionLogo name="$" size={36} /><span>Efectivo</span>
            </button>
          </div>
        </div>

        {choice && (
          <>
            <small>2 · Detalles</small>
            {choice.kind === "other" && (
              <input name="other" placeholder="Nombre de la entidad o app (ej. Banco X, Fintech Y)" required autoFocus />
            )}
            <div className="row">
              <select value={type} onChange={(e) => setType(e.target.value as AccountType)} disabled={choice.kind === "cash"}>
                {types.map((t) => <option key={t} value={t}>{ACCOUNT_TYPES[t]}</option>)}
              </select>
              <input name="name" placeholder="Nombre de la cuenta (opcional)" />
              <input name="balance" type="number" step="0.01" min={isCard ? 0 : undefined}
                placeholder={isCard ? "Deuda actual de la tarjeta" : type === "investment" ? "Valor actual invertido" : "Saldo actual"} />
            </div>
            {isCard && (
              <div className="row">
                <input name="limit" type="number" step="0.01" min="0" placeholder="Cupo total" />
                <input name="rate" type="number" step="0.01" min="0" placeholder="Tasa de interés %" />
                <select name="rate_type">
                  <option value="EA">Efectiva anual</option>
                  <option value="MV">Mensual vencida</option>
                  <option value="NA">Nominal anual</option>
                </select>
                <input name="payment" type="number" step="0.01" min="0" placeholder="Pago mensual habitual" />
              </div>
            )}
          </>
        )}

        {error && <p className="error">{error}</p>}
        <div className="row modal-actions">
          <button type="button" className="link" onClick={onClose}>Cancelar</button>
          <button disabled={busy || !choice}>{busy ? "…" : "Guardar cuenta"}</button>
        </div>
      </motion.form>
    </motion.div>
  );
}
