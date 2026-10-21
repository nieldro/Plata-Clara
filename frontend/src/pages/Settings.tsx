import { FormEvent, useEffect, useState } from "react";
import { api, download, setToken } from "../api";
import NotificationPrefs from "../components/NotificationPrefs";

type Me = { id: number; email: string; name: string };

export default function Settings() {
  const [me, setMe] = useState<Me | null>(null);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [dataMsg, setDataMsg] = useState("");
  const [delMsg, setDelMsg] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => { api.get<Me>("/auth/me").then(setMe); }, []);

  async function changePassword(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    if (f.get("new") !== f.get("again")) return setPwMsg({ ok: false, text: "La contraseña nueva no coincide en los dos campos" });
    setBusy("pw");
    try {
      const r = await api.post<{ access_token: string }>("/account/password", {
        current_password: f.get("current"), new_password: f.get("new"),
      });
      setToken(r.access_token); // esta sesión sigue; las demás se cierran
      form.reset();
      setPwMsg({ ok: true, text: "Listo. Cambiaste tu contraseña y cerramos tus otras sesiones." });
    } catch (err) {
      setPwMsg({ ok: false, text: (err as Error).message });
    } finally {
      setBusy("");
    }
  }

  const [sessionMsg, setSessionMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function logoutEverywhere() {
    if (!confirm("Se cerrará tu sesión en todos los demás dispositivos. Esta seguirá abierta. ¿Continuar?")) return;
    setBusy("sessions");
    try {
      const r = await api.post<{ access_token: string }>("/account/logout-all");
      setToken(r.access_token);
      setSessionMsg({ ok: true, text: "Listo: cerramos las sesiones de los demás dispositivos." });
    } catch (err) {
      setSessionMsg({ ok: false, text: (err as Error).message });
    } finally {
      setBusy("");
    }
  }

  async function exportData() {
    setBusy("data");
    try {
      await download("/account/export", "plata-clara-datos.json");
      setDataMsg("Descargado. Guárdalo en un lugar seguro: contiene todos tus movimientos.");
    } catch (err) {
      setDataMsg((err as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function deleteAccount(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (String(f.get("confirm")).trim().toUpperCase() !== "BORRAR") return setDelMsg("Escribe BORRAR para confirmar");
    if (!confirm("Última advertencia: se borrarán tu cuenta y TODOS tus datos para siempre. ¿Continuar?")) return;
    setBusy("del");
    try {
      await api.post("/account/delete", { password: f.get("password") });
      setToken(null);
      location.reload();
    } catch (err) {
      setDelMsg((err as Error).message);
      setBusy("");
    }
  }

  return (
    <>
      <div className="card">
        <h2>Mi cuenta</h2>
        <p className="empty">{me ? <><b>{me.name}</b> · {me.email}</> : "Cargando…"}</p>
      </div>

      <NotificationPrefs />

      <div className="card">
        <h2>Cambiar contraseña</h2>
        <p className="empty">Al cambiarla se cierran las sesiones abiertas en otros dispositivos.</p>
        <form className="row" onSubmit={changePassword}>
          <input name="current" type="password" placeholder="Contraseña actual" required autoComplete="current-password" />
          <input name="new" type="password" placeholder="Nueva (mínimo 8)" minLength={8} required autoComplete="new-password" />
          <input name="again" type="password" placeholder="Repite la nueva" minLength={8} required autoComplete="new-password" />
          <button disabled={busy === "pw"}>{busy === "pw" ? "…" : "Cambiar contraseña"}</button>
        </form>
        {pwMsg && <p className={pwMsg.ok ? "ok-msg" : "error"}>{pwMsg.text}</p>}
      </div>

      <div className="card">
        <h2>Sesiones</h2>
        <p className="empty">¿Perdiste un celular o entraste desde un computador que no es tuyo? Cierra la sesión en todos los demás dispositivos sin cambiar tu contraseña.</p>
        <div className="row"><button className="btn-ghost" disabled={busy === "sessions"} onClick={logoutEverywhere}>Cerrar sesión en los demás dispositivos</button></div>
        {sessionMsg && <p className={sessionMsg.ok ? "ok-msg" : "error"}>{sessionMsg.text}</p>}
      </div>

      <div className="card">
        <h2>Mis datos</h2>
        <p className="empty">
          Descarga una copia completa de tu información (cuentas, movimientos, metas, préstamos…) en un archivo JSON.
          Para una hoja de cálculo, usa los botones «Excel» y «CSV» del historial en «Cuentas y movimientos».
        </p>
        <div className="row"><button className="btn-ghost" disabled={busy === "data"} onClick={exportData}>⬇ Descargar todos mis datos</button></div>
        {dataMsg && <p className="hint">{dataMsg}</p>}
      </div>

      <div className="card danger">
        <h2>Borrar mi cuenta</h2>
        <p className="empty">Elimina tu cuenta y todos tus datos, incluidos los recibos. <b>No se puede deshacer</b>; descarga tus datos antes.</p>
        <form className="row" onSubmit={deleteAccount}>
          <input name="password" type="password" placeholder="Tu contraseña" required autoComplete="current-password" />
          <input name="confirm" placeholder="Escribe BORRAR" required autoComplete="off" />
          <button className="btn-danger" disabled={busy === "del"}>{busy === "del" ? "Borrando…" : "Borrar para siempre"}</button>
        </form>
        {delMsg && <p className="error">{delMsg}</p>}
      </div>
    </>
  );
}
