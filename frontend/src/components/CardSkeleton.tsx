/** Hueco con la forma de una tarjeta mientras sus datos llegan, para que la pantalla no «salte» al aparecer. */
export default function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card skeleton" role="status" aria-label="Cargando">
      <span className="sk-line sk-title" />
      {Array.from({ length: lines }, (_, i) => <span key={i} className="sk-line" style={{ width: `${92 - i * 14}%` }} />)}
    </div>
  );
}
