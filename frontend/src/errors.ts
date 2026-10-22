export const NETWORK_ERROR = "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";

export const TIMEOUT_ERROR = "El servidor tardó demasiado en responder. Inténtalo de nuevo en un momento.";

type ValidationItem = { msg?: unknown };

/** Mensaje en español para el usuario a partir de lo que respondió la API. */
export function messageFor(status: number, body: unknown): string {
  const detail = body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;

  if (Array.isArray(detail)) {
    // errores de validación de FastAPI: [{msg: "Value error, ..."}]
    const text = detail
      .map((d: ValidationItem) => String(d?.msg ?? "").replace(/^Value error, /, ""))
      .filter(Boolean)
      .join(" · ");
    if (text) return text;
  }
  if (typeof detail === "string" && detail.trim()) return detail;

  // Sin mensaje de la API (por ejemplo, una página de error de nginx): se explica según el código.
  if (status === 413) return "El archivo es demasiado grande.";
  if (status === 429) return "Demasiados intentos. Espera un momento e inténtalo de nuevo.";
  if (status === 502 || status === 503 || status === 504) {
    return "El servidor no está disponible en este momento. Inténtalo de nuevo en unos minutos.";
  }
  if (status >= 500) return "Ocurrió un error inesperado en el servidor. Inténtalo de nuevo.";
  if (status === 404) return "No se encontró lo que buscabas.";
  return "No se pudo completar la solicitud.";
}
