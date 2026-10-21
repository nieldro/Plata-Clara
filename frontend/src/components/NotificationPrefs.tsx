import { useEffect, useState } from "react";
import { api } from "../api";

type Kind = { kind: string; label: string; enabled: boolean };

export default function NotificationPrefs() {
  const [kinds, setKinds] = useState<Kind[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { api.get<{ kinds: Kind[] }>("/notifications/preferences").then((r) => setKinds(r.kinds)).catch((e) => setError(e.message)); }, []);

  async function toggle(k: Kind) {
    if (!kinds) return;
    setBusy(true);
    setError("");
    const next = kinds.map((x) => (x.kind === k.kind ? { ...x, enabled: !x.enabled } : x));
    setKinds(next); // se refleja al instante; si falla, se revierte
    try {
      const r = await api.put<{ kinds: Kind[] }>("/notifications/preferences", { muted: next.filter((x) => !x.enabled).map((x) => x.kind) });
      setKinds(r.kinds);
    } catch (err) {
      setKinds(kinds);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Avisos</h2>
      <p className="empty">Elige de qué quieres que te avise la campana. Lo que silencies deja de llegar y desaparece de la lista.</p>
      {kinds === null && !error && <p className="empty">Cargando…</p>}
      <ul className="switches">
        {kinds?.map((k) => (
          <li key={k.kind}>
            <label>
              <input type="checkbox" role="switch" checked={k.enabled} disabled={busy} onChange={() => toggle(k)} />
              <span>{k.label}</span>
            </label>
          </li>
        ))}
      </ul>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
