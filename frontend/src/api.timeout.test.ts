import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { NETWORK_ERROR, TIMEOUT_ERROR } from "./errors";

// fetch que se queda esperando hasta que lo cancelan, como una conexión colgada
const hangingFetch = (_url: string, init?: RequestInit) =>
  new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("cancelado", "AbortError")));
  });

describe("tiempo de espera de las peticiones", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("localStorage", { getItem: () => null, setItem: () => {}, removeItem: () => {} });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("corta una conexión colgada y lo explica con un mensaje claro", async () => {
    vi.stubGlobal("fetch", vi.fn(hangingFetch));
    const pending = expect(api.get("/accounts")).rejects.toThrow(TIMEOUT_ERROR);
    await vi.advanceTimersByTimeAsync(30_000);
    await pending;
  });

  it("subir un archivo tiene más margen que una consulta normal", async () => {
    vi.stubGlobal("fetch", vi.fn(hangingFetch));
    let settled = false;
    const upload = api.upload("/imports", new FormData()).catch((e: Error) => { settled = true; return e; });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(((await upload) as Error).message).toBe(TIMEOUT_ERROR);
  });

  it("un fallo de red sigue diciendo que no hay conexión, no que se agotó el tiempo", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(api.get("/accounts")).rejects.toThrow(NETWORK_ERROR);
  });
});
