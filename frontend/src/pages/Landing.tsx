import {
  motion, MotionValue, useScroll, useSpring, useTransform,
} from "framer-motion";
import { useEffect, useRef, useState } from "react";
import CountUp from "../components/CountUp";
import { Logo } from "../components/Icons";
import Reveal from "../components/Reveal";
import { money } from "../api";
import { EASE } from "../theme";

type Props = { onAuth: (mode: "login" | "register") => void };

const FEATURES = [
  {
    n: "01", title: "Cada movimiento, en su lugar",
    text: "Registra ingresos y gastos por cuenta y categoría. El saldo de cada cuenta se calcula solo y el resumen mensual te muestra a dónde se fue el dinero.",
  },
  {
    n: "02", title: "Tarjetas y créditos, sin sorpresas",
    text: "Ingresa tu tasa (EA, mensual o nominal) y ve la cuota, el interés de cada mes y cuánto pagarás en total. Si el pago no alcanza ni para los intereses, te lo advertimos.",
  },
  {
    n: "03", title: "Abona extra y ve la diferencia",
    text: "Simula un abono mensual adicional y descubre cuántos meses y cuánto interés te ahorras. Decidir con números cambia todo.",
  },
  {
    n: "04", title: "Metas de ahorro con fecha",
    text: "Define el monto, la fecha y cuánto rinde tu dinero. Te decimos cuánto ahorrar cada mes para llegar, con una barra que muestra tu avance.",
  },
];

const STATS = [
  { v: 100, suffix: "%", label: "Gratuito, sin anuncios" },
  { v: 3, suffix: "", label: "Tipos de tasa: EA, MV y NA" },
  { v: 600, suffix: "", label: "Meses de proyección" },
];

const STATEMENT =
  "Cada peso que debes tiene un precio. Plata Clara te lo muestra mes a mes y te dice cuánto te ahorras si abonas un poco más.";

function Word({ children, progress, range }: { children: string; progress: MotionValue<number>; range: [number, number] }) {
  const opacity = useTransform(progress, range, [0.14, 1]);
  return <motion.span style={{ opacity }}>{children} </motion.span>;
}

/** Texto que se "enciende" palabra por palabra al hacer scroll. */
function WordReveal({ text }: { text: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.85", "end 0.45"] });
  const words = text.split(" ");
  return (
    <p ref={ref} className="wordreveal">
      {words.map((w, i) => (
        <Word key={i} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]}>
          {w}
        </Word>
      ))}
    </p>
  );
}

export default function Landing({ onAuth }: Props) {
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress: pageProgress } = useScroll();
  const bar = useSpring(pageProgress, { stiffness: 120, damping: 30 });

  const { scrollYProgress: hero } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const orbA = useTransform(hero, [0, 1], [0, 260]);
  const orbB = useTransform(hero, [0, 1], [0, -140]);
  const textY = useTransform(hero, [0, 1], [0, 90]);
  const textOpacity = useTransform(hero, [0, 0.7], [1, 0]);
  const mockY = useTransform(hero, [0, 1], [0, -60]);

  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 40);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  return (
    <div className="landing">
      <motion.div className="scrollbar" style={{ scaleX: bar }} />

      <nav className={`lnav ${scrolled ? "solid" : ""}`}>
        <div className="brand"><Logo /> <span>Plata Clara</span></div>
        <div className="lnav-actions">
          <button className="link" onClick={() => onAuth("login")}>Entrar</button>
          <button className="btn" onClick={() => onAuth("register")}>Comenzar</button>
        </div>
      </nav>

      {/* HERO */}
      <section className="hero" ref={heroRef}>
        <motion.div className="orb orb-a" style={{ y: orbA }} />
        <motion.div className="orb orb-b" style={{ y: orbB }} />
        <div className="hero-inner">
          <motion.div style={{ y: textY, opacity: textOpacity }} className="hero-text">
            <motion.span className="eyebrow" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: EASE }}>
              Finanzas personales, con elegancia
            </motion.span>
            <motion.h1 initial={{ opacity: 0, y: 36 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1.1, delay: 0.1, ease: EASE }}>
              Tu dinero, <em>con claridad.</em>
            </motion.h1>
            <motion.p className="lead" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 0.3, ease: EASE }}>
              Registra cada movimiento, entiende tus tarjetas y créditos al detalle y planea tu ahorro con cifras reales.
            </motion.p>
            <motion.div className="cta-row" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 0.5, ease: EASE }}>
              <button className="btn btn-lg" onClick={() => onAuth("register")}>Crear mi cuenta</button>
              <button className="btn btn-ghost btn-lg" onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}>
                Ver cómo funciona
              </button>
            </motion.div>
          </motion.div>

          <motion.div className="mock-wrap" style={{ y: mockY }}>
            <motion.div
              className="mock card"
              initial={{ opacity: 0, y: 60, rotate: -2 }}
              animate={{ opacity: 1, y: 0, rotate: 0 }}
              transition={{ duration: 1.3, delay: 0.4, ease: EASE }}
            >
              <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}>
                <small>Patrimonio neto</small>
                <b className="mock-amount"><CountUp value={12480000} format={(n) => money(n)} duration={2.4} /></b>
                <svg viewBox="0 0 240 80" className="spark">
                  <defs>
                    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0" stopColor="#c9a96a" stopOpacity=".35" />
                      <stop offset="1" stopColor="#c9a96a" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <path d="M0 70 C30 66 50 40 80 46 S130 20 160 28 S210 8 240 12 V80 H0Z" fill="url(#g)" />
                  <motion.path
                    d="M0 70 C30 66 50 40 80 46 S130 20 160 28 S210 8 240 12"
                    fill="none" stroke="#c9a96a" strokeWidth="2" strokeLinecap="round"
                    initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 2.2, delay: 0.8, ease: EASE }}
                  />
                </svg>
                <div className="mock-row"><span>Cuota crédito</span><span className="neg">− {money(888488)}</span></div>
                <div className="mock-row"><span>Meta: viaje</span><span className="pos">62%</span></div>
              </motion.div>
            </motion.div>
          </motion.div>
        </div>
        <motion.div className="scroll-hint" animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 2.4, repeat: Infinity }}>
          Desliza
        </motion.div>
      </section>

      {/* CIFRAS */}
      <section className="stats">
        {STATS.map((s, i) => (
          <Reveal key={s.label} delay={i * 0.12}>
            <div className="stat">
              <b><CountUp value={s.v} />{s.suffix}</b>
              <span>{s.label}</span>
            </div>
          </Reveal>
        ))}
      </section>

      {/* FRASE QUE SE ENCIENDE */}
      <section className="statement"><WordReveal text={STATEMENT} /></section>

      {/* FUNCIONES (título fijo + tarjetas que suben) */}
      <section className="features" id="features">
        <div className="sticky">
          <Reveal>
            <span className="eyebrow">Qué incluye</span>
            <h2>Todo lo que tu dinero <em>necesita saber.</em></h2>
          </Reveal>
        </div>
        <div className="feature-list">
          {FEATURES.map((f) => (
            <Reveal key={f.n}>
              <article className="card feature">
                <span className="num-serif">{f.n}</span>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* CIERRE */}
      <section className="closing">
        <Reveal>
          <h2>Empieza hoy. <em>Es gratis.</em></h2>
          <p className="lead">Sin tarjeta, sin anuncios. Tus datos son tuyos.</p>
          <button className="btn btn-lg" onClick={() => onAuth("register")}>Crear mi cuenta</button>
        </Reveal>
      </section>

      <footer className="lfoot">
        <div className="brand"><Logo size={22} /> <span>Plata Clara</span></div>
        <small>Proyecto personal · Hecho con FastAPI, React y PostgreSQL</small>
      </footer>
    </div>
  );
}
