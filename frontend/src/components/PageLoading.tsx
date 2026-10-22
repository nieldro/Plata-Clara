/** Lo que se ve mientras se descarga una pantalla. */
export default function PageLoading() {
  return (
    <div className="page-loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden />
      <span>Cargando…</span>
    </div>
  );
}
