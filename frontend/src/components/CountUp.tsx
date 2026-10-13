import { animate, useInView } from "framer-motion";
import { useEffect, useRef } from "react";
import { EASE } from "../theme";

type Props = { value: number; format?: (n: number) => string; duration?: number };

/** Número que cuenta desde 0 hasta `value` cuando se hace visible. */
export default function CountUp({ value, format = (n) => String(Math.round(n)), duration = 1.8 }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const visible = useInView(ref, { once: true });

  useEffect(() => {
    if (!visible) return;
    const controls = animate(0, value, {
      duration,
      ease: EASE,
      onUpdate: (v) => {
        if (ref.current) ref.current.textContent = format(v);
      },
    });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, value, duration]);

  return <span ref={ref}>{format(0)}</span>;
}
