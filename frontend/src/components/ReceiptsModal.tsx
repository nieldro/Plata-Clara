import { motion } from "framer-motion";
import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { api, Attachment, getBlob, money, Tx } from "../api";
import useEscape from "../hooks/useEscape";
import { EASE } from "../theme";

const MAX_MB = 5;
const kb = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

export default function ReceiptsModal({ tx, onClose, onChanged }: { tx: Tx; onClose: () => void; onChanged: () => void }) {
  useEscape(onClose);
  const [items, setItems] = useState<Attachment[]>([]);
  const [thumbs, setThumbs] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => setItems(await api.get<Attachment[]>(`/transactions/${tx.id}/attachments`)), [tx.id]);
  useEffect(() => { load().catch((e) => setError(e.message)); }, [load]);

  // Las imágenes están protegidas: se piden con el token y se muestran desde una URL local temporal.
  useEffect(() => {
    let cancelled = false;
    const created: string[] = [];
    (async () => {
      for (const a of items) {
        if (!a.content_type.startsWith("image/") || thumbs[a.id]) continue;
        try {
          const url = URL.createObjectURL(await getBlob(`/attachments/${a.id}/file`));
          created.push(url);
          if (!cancelled) setThumbs((t) => ({ ...t, [a.id]: url }));
        } catch { /* se verá sin miniatura */ }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);
  useEffect(() => () => Object.values(thumbs).forEach(URL.revokeObjectURL), [thumbs]);

  async function pick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) return setError(`El archivo supera los ${MAX_MB} MB`);
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api.upload(`/transactions/${tx.id}/attachments`, form);
      await load();
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function open(a: Attachment) {
    try {
      const url = URL.createObjectURL(await getBlob(`/attachments/${a.id}/file`));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(a: Attachment) {
    if (!confirm(`¿Borrar «${a.filename}»?`)) return;
    await api.del(`/attachments/${a.id}`);
    setThumbs((t) => { const n = { ...t }; delete n[a.id]; return n; });
    await load();
    onChanged();
  }

  return (
    <motion.div className="modal-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.div className="card modal wide" data-lenis-prevent
        initial={{ opacity: 0, y: 30, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }} transition={{ duration: 0.5, ease: EASE }}>
        <h2>Recibos</h2>
        <small>{tx.note || "Movimiento"} · {tx.date} · {money(tx.amount)}</small>

        {items.length === 0 && <p className="empty">Aún no hay recibos. Sube una foto o el PDF de la factura.</p>}
        <div className="receipts">
          {items.map((a) => (
            <div className="receipt" key={a.id}>
              <button className="thumb" onClick={() => open(a)} title="Abrir">
                {thumbs[a.id] ? <img src={thumbs[a.id]} alt={a.filename} /> : <span>{a.content_type === "application/pdf" ? "PDF" : "…"}</span>}
              </button>
              <small title={a.filename}>{a.filename}</small>
              <small>{kb(a.size)}</small>
              <button className="link" onClick={() => remove(a)}>Borrar</button>
            </div>
          ))}
        </div>

        {error && <p className="error">{error}</p>}
        <div className="row modal-actions">
          <button type="button" className="link" onClick={onClose}>Cerrar</button>
          <label className={`btn-upload ${busy || items.length >= 5 ? "off" : ""}`}>
            {busy ? "Subiendo…" : items.length >= 5 ? "Máximo 5 archivos" : "＋ Foto o PDF"}
            {/* en el celular abre la cámara o la galería */}
            <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" capture="environment"
              hidden disabled={busy || items.length >= 5} onChange={pick} />
          </label>
        </div>
      </motion.div>
    </motion.div>
  );
}
