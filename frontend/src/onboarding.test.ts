import { describe, expect, it } from "vitest";
import { isOnboardingComplete, onboardingSteps } from "./onboarding";

describe("onboardingSteps", () => {
  it("con una cuenta nueva, ningún paso está hecho", () => {
    const steps = onboardingSteps({ accounts: 0, transactions: 0, budgets: 0, goals: 0 });
    expect(steps.map((s) => s.done)).toEqual([false, false, false, false]);
    expect(isOnboardingComplete(steps)).toBe(false);
  });

  it("marca solo los pasos que ya tienen datos", () => {
    const steps = onboardingSteps({ accounts: 2, transactions: 14, budgets: 0, goals: 0 });
    expect(steps.filter((s) => s.done).map((s) => s.key)).toEqual(["accounts", "transactions"]);
  });

  it("está completo cuando todo tiene al menos uno", () => {
    expect(isOnboardingComplete(onboardingSteps({ accounts: 1, transactions: 1, budgets: 1, goals: 1 }))).toBe(true);
  });
});
