import { motion } from "framer-motion";
import { FormEvent, useState } from "react";
import { api } from "../api";
import { Logo } from "../components/Icons";
import useEscape from "../hooks/useEscape";
import { EASE } from "../theme";

type Props = {
  mode: "login" | "register";
  onMode: (m: "login" | "register") => void;
  onClose: () => void;
  onDone: () => void;
};

export default function AuthModal({ mode, onMode, onClose, onDone }: Props) {
  useEscape(onClose);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const register = mode === "register";

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get("email"));
    const password = String(f.get("password"));
    setBusy(true);
    setError("");
    try {
      if (register) await api.post("/auth/register", { email, password, name: f.get("name") });
      await api.login(email, password);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      className="modal-bg"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.form
        className="card modal"
        onSubmit={submit}
        initial={{ opacity: 0, y: 30, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }}
        transition={{ duration: 0.5, ease: EASE }}
      >
        <Logo size={36} />
        <h2>{register ? "Crea tu cuenta" : "Bienvenido de nuevo"}</h2>
        {register && <input name="name" placeholder="Nombre" required autoFocus />}
        <input name="email" type="email" placeholder="Correo" required autoFocus={!register} />
        <input name="password" type="password" placeholder="Contraseña (mínimo 8)" minLength={8} required />
        {error && <p className="error">{error}</p>}
        <button className="btn btn-lg" disabled={busy}>{busy ? "…" : register ? "Crear cuenta" : "Entrar"}</button>
        <button type="button" className="link" onClick={() => onMode(register ? "login" : "register")}>
          {register ? "Ya tengo cuenta" : "Crear una cuenta"}
        </button>
      </motion.form>
    </motion.div>
  );
}
