import { Component, ErrorInfo, ReactNode } from "react";

type Props = {
  children: ReactNode;
  /** Cuando cambia (por ejemplo, al cambiar de sección) el error se descarta y se vuelve a intentar. */
  resetKey?: string;
  /** «section»: falla una pantalla y el menú sigue; «app»: falla todo. */
  scope?: "section" | "app";
};
type State = { error: Error | null };

/** Si algo falla al dibujarse, en vez de una pantalla en blanco muestra qué hacer. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Error al dibujar la pantalla:", error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    const whole = this.props.scope === "app";
    return (
      <div className="card crash" role="alert">
        <h2>Algo salió mal</h2>
        <p className="empty">
          {whole
            ? "La aplicación tuvo un problema inesperado. Tus datos están a salvo."
            : "Esta pantalla tuvo un problema inesperado, pero el resto de la app sigue funcionando. Tus datos están a salvo."}
        </p>
        <div className="row">
          <button onClick={() => (whole ? location.reload() : this.setState({ error: null }))}>
            {whole ? "Recargar la página" : "Intentar de nuevo"}
          </button>
          {!whole && <button className="btn-ghost" onClick={() => location.reload()}>Recargar la página</button>}
        </div>
        <details className="cols"><summary>Detalle técnico</summary><pre>{this.state.error.message}</pre></details>
      </div>
    );
  }
}
