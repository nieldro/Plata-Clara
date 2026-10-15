import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { EASE } from "../theme";
import { Icons } from "./Icons";

type Notif = { id: number; kind: string; title: string; body: string; read: boolean; created_at: string };
type Payload = { unread: number; new: number; items: Notif[] };

const POLL_MS = 2 * 60 * 1000;
const store = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } },
};
const canBrowserNotify = typeof Notification !== "undefined";
const KIND_LABEL: Record<string, string> = { budget: "Presupuesto", due: "Pago", goal: "Meta", recurring: "Recurrente" };

const when = (s: string) =>
  new Date(s.endsWith("Z") ? s : `${s}Z`).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Payload>({ unread: 0, new: 0, items: [] });
  const [browserOn, setBrowserOn] = useState(
    () => canBrowserNotify && Notification.permission === "granted" && store.get("notif-browser") === "1",
  );
  const lastSeen = useRef(Number(store.get("notif-last") ?? 0));

  const refresh = useCallback(async () => {
    try {
      const r = await api.post<Payload>("/notifications/refresh");
      setData(r);
      const maxId = Math.max(0, ...r.items.map((i) => i.id));
      if (browserOn) {
        r.items.filter((i) => !i.read && i.id > lastSeen.current).reverse()
          .forEach((i) => new Notification(i.title, { body: i.body, icon: "/favicon.ico" }));
      }
      lastSeen.current = Math.max(lastSeen.current, maxId);
      store.set("notif-last", String(lastSeen.current));
    } catch { /* sin conexión: se reintenta en el siguiente ciclo */ }
  }, [browserOn]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  async function enableBrowser() {
    if (!canBrowserNotify) return;
    const perm = await Notification.requestPermission();
    if (perm === "granted") {
      lastSeen.current = Math.max(0, ...data.items.map((i) => i.id)); // no avisar lo que ya existe
      store.set("notif-last", String(lastSeen.current));
      store.set("notif-browser", "1");
      setBrowserOn(true);
    }
  }

  const reload = async () => setData({ ...(await api.get<Payload>("/notifications")) });
  const markAll = async () => { await api.post("/notifications/read-all"); reload(); };
  const markOne = async (n: Notif) => { if (!n.read) { await api.post(`/notifications/${n.id}/read`); reload(); } };
  const remove = async (n: Notif) => { await api.del(`/notifications/${n.id}`); reload(); };

  return (
    <div className="bell-wrap">
      <button className="bell" onClick={() => setOpen(!open)} aria-label="Notificaciones">
        {Icons.bell}
        {data.unread > 0 && <span className="badge">{data.unread > 9 ? "9+" : data.unread}</span>}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="bell-backdrop" onClick={() => setOpen(false)} />
            <motion.div
              className="card bell-panel"
              initial={{ opacity: 0, y: -8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }} transition={{ duration: 0.3, ease: EASE }}
            >
              <div className="bell-head">
                <h2>Notificaciones</h2>
                {data.unread > 0 && <button className="link" onClick={markAll}>Marcar todo como leído</button>}
              </div>
              <div className="bell-list" data-lenis-prevent>
                {data.items.length === 0 && <p className="empty">Todo en orden. Aquí te avisaremos de presupuestos, pagos y metas.</p>}
                {data.items.map((n) => (
                  <div key={n.id} className={`notif ${n.read ? "" : "unread"} k-${n.kind}`} onClick={() => markOne(n)}>
                    <div className="notif-top">
                      <small>{KIND_LABEL[n.kind] ?? n.kind} · {when(n.created_at)}</small>
                      <button className="link" onClick={(e) => { e.stopPropagation(); remove(n); }}>✕</button>
                    </div>
                    <b>{n.title}</b>
                    <p>{n.body}</p>
                  </div>
                ))}
              </div>
              {canBrowserNotify && !browserOn && Notification.permission !== "denied" && (
                <button className="btn-ghost" onClick={enableBrowser}>Activar avisos del navegador</button>
              )}
              {canBrowserNotify && Notification.permission === "denied" && (
                <small>Los avisos del navegador están bloqueados en la configuración del sitio.</small>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
