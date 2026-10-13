import { AnimatePresence } from "framer-motion";
import { useState } from "react";
import { getToken, setToken } from "./api";
import Shell from "./components/Shell";
import Landing from "./pages/Landing";
import AuthModal from "./pages/Login";

export default function App() {
  const [logged, setLogged] = useState(!!getToken());
  const [auth, setAuth] = useState<null | "login" | "register">(null);

  if (logged) {
    return <Shell onLogout={() => { setToken(null); setLogged(false); }} />;
  }
  return (
    <>
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
    </>
  );
}
