import { useState } from "react";
import { Institution } from "../api";

type Props = { inst?: Institution | null; name?: string | null; size?: number };

const initials = (s: string) =>
  s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";

/**
 * Logo de la entidad. Usa el favicon del sitio de la entidad (servicio gratuito de Google);
 * si no carga o la entidad no está en el catálogo, muestra un monograma con su color.
 */
export default function InstitutionLogo({ inst, name, size = 44 }: Props) {
  const [failed, setFailed] = useState(false);
  const label = inst?.name ?? name ?? "?";
  const style = { width: size, height: size, borderRadius: Math.round(size * 0.28) };

  if (inst && !failed) {
    return (
      <img
        className="logo-img"
        style={style}
        src={`https://www.google.com/s2/favicons?domain=${inst.domain}&sz=128`}
        alt={label}
        loading="lazy"
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <span
      className="logo-mono"
      style={{ ...style, fontSize: size * 0.38, background: inst ? `${inst.color}26` : undefined, color: inst?.color }}
      aria-label={label}
    >
      {initials(label)}
    </span>
  );
}
