import { motion } from "framer-motion";
import { ReactNode } from "react";
import { EASE } from "../theme";

type Props = { children: ReactNode; delay?: number; y?: number; className?: string };

/** Aparece suavemente (subiendo) la primera vez que entra en pantalla. */
export default function Reveal({ children, delay = 0, y = 32, className }: Props) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.9, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
