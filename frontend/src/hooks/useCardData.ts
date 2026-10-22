import { useEffect, useState } from "react";
import { api } from "../api";

/**
 * Carga los datos de una tarjeta del Resumen. Mientras llegan por primera vez `loading` es true (para mostrar un esqueleto);
 * si la petición falla, `data` queda en null y la tarjeta simplemente no se muestra. Si `path` cambia (otro rango, otro mes),
 * se siguen mostrando los datos anteriores hasta que lleguen los nuevos.
 */
export default function useCardData<T>(path: string) {
  const [state, setState] = useState<{ data: T | null; failed: boolean }>({ data: null, failed: false });

  useEffect(() => {
    let current = true; // ignora la respuesta de una petición vieja si ya se pidió otra
    api.get<T>(path)
      .then((data) => { if (current) setState({ data, failed: false }); })
      .catch(() => { if (current) setState({ data: null, failed: true }); });
    return () => { current = false; };
  }, [path]);

  return { data: state.data, loading: !state.data && !state.failed };
}
