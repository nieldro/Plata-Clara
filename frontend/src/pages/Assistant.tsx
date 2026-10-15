import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api } from "../api";
import { EASE } from "../theme";

type Insight = { id: string; level: "warn" | "info" | "good"; title: string; text: string };

const LABEL = { warn: "Atención", info: "Dato útil", good: "Vas bien" };

export default function Assistant() {
  const [items, setItems] = useState<Insight[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<{ insights: Insight[] }>("/assistant").then((r) => setItems(r.insights)).catch((e) => setError(e.message));
  }, []);

  const warns = items?.filter((i) => i.level === "warn").length ?? 0;

  return (
    <>
      <div className="card assistant-head">
        <h2>Lo que veo en tus finanzas</h2>
        <p className="empty">
          {items === null
            ? "Analizando tus datos…"
            : warns > 0
              ? `Hay ${warns} ${warns === 1 ? "punto" : "puntos"} que merecen tu atención.`
              : "Todo se ve en orden. Sigue así."}
        </p>
      </div>
      {error && <p className="error">{error}</p>}

      <div className="insights">
        {items?.map((i, n) => (
          <motion.article
            key={i.id}
            className={`card insight ${i.level}`}
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: n * 0.07, ease: EASE }}
          >
            <span className="insight-dot" />
            <div>
              <small>{LABEL[i.level]}</small>
              <h3>{i.title}</h3>
              <p>{i.text}</p>
            </div>
          </motion.article>
        ))}
      </div>
    </>
  );
}
