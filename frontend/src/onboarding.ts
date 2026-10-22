export type Progress = { accounts: number; transactions: number; budgets: number; goals: number };

export type Step = { key: keyof Progress; title: string; hint: string; done: boolean };

/** Los pasos para empezar a usar la app y cuáles ya están hechos. */
export function onboardingSteps(p: Progress): Step[] {
  return [
    { key: "accounts", title: "Agrega tu primera cuenta", hint: "En «Cuentas y movimientos»: tu banco, billetera o efectivo.", done: p.accounts > 0 },
    { key: "transactions", title: "Registra un movimiento", hint: "Un gasto o ingreso; también puedes importar un extracto.", done: p.transactions > 0 },
    { key: "budgets", title: "Define un presupuesto", hint: "En «Presupuestos»: un tope mensual para una categoría.", done: p.budgets > 0 },
    { key: "goals", title: "Crea una meta de ahorro", hint: "En «Ahorro»: cuánto quieres juntar y para cuándo.", done: p.goals > 0 },
  ];
}

export const isOnboardingComplete = (steps: Step[]) => steps.every((s) => s.done);
