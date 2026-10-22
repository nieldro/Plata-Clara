import { AnimatePresence } from "framer-motion";
import { lazy, Suspense, useState } from "react";
import { getToken, setToken } from "./api";
import PageLoading from "./components/PageLoading";

// Quien no ha iniciado sesión no descarga la app, y quien sí la inició no descarga la página de presentación.
const Shell = lazy(() => import("./components/Shell"));
const Landing = lazy(() => import("./pages/Landing"));
const AuthModal = lazy(() => import("./pages/Login"));

export default function App() {
  const [logged, setLogged] = useState(!!getToken());
  const [auth, setAuth] = useState<null | "login" | "register">(null);

  if (logged) {
    return (
      <Suspense fallback={<PageLoading />}>
        <Shell onLogout={() => { setToken(null); setLogged(false); }} />
      </Suspense>
    );
  }
  return (
    <Suspense fallback={<PageLoading />}>
      <Landing onAuth={setAuth} />
      <AnimatePresence>
        {auth && (
          <AuthModal
            key="auth"
            mode={auth}
            onMode={setAuth}
            onClose={() => setAuth(null)}
            onDone={() => { setLogged(true); setAuth(null); }}
          />
        )}
      </AnimatePresence>
    </Suspense>
  );
}
