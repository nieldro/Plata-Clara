import { useEffect, useState } from "react";
import { api, getPage } from "../api";
import { isOnboardingComplete, onboardingSteps, Progress } from "../onboarding";

const DISMISS_KEY = "onboarding-dismissed";

const dismissed = () => { try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; } };

/** Lista de primeros pasos en el Resumen; desaparece sola al completarla, o cuando se descarta. */
export default function OnboardingCard() {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [hidden, setHidden] = useState(dismissed());

  useEffect(() => {
    if (hidden) return;
    let current = true;
    Promise.all([
      api.get<unknown[]>("/accounts"),
      getPage<unknown>("/transactions?limit=1"),
      api.get<{ items: unknown[] }>("/budgets"),
      api.get<unknown[]>("/savings"),
    ])
      .then(([accounts, tx, budgets, goals]) => {
        if (current) setProgress({ accounts: accounts.length, transactions: tx.total, budgets: budgets.items.length, goals: goals.length });
      })
      .catch(() => { /* sin datos no se muestra: es solo una ayuda */ });
    return () => { current = false; };
  }, [hidden]);

  if (hidden || !progress) return null;
  const steps = onboardingSteps(progress);
  if (isOnboardingComplete(steps)) return null;
  const done = steps.filter((s) => s.done).length;

  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* si no se puede guardar, se oculta solo hasta recargar */ }
    setHidden(true);
  };

  return (
    <div className="card onboarding">
      <div className="onboarding-head">
        <h2>Empieza por aquí <small>{done} de {steps.length}</small></h2>
        <button className="btn-ghost" onClick={dismiss}>Ocultar</button>
      </div>
      <progress max={steps.length} value={done} aria-label="Primeros pasos completados" />
      <ul className="steps">
        {steps.map((s) => (
          <li key={s.key} className={s.done ? "done" : ""}>
            <span className="step-mark" aria-hidden>{s.done ? "✓" : ""}</span>
            <div>
              <b>{s.title}</b>
              <small className="block">{s.hint}</small>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
