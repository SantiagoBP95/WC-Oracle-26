import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "No se pudo iniciar sesión"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div className="card w-full max-w-sm p-8">
        <div className="mb-6 text-center">
          <div className="text-4xl">⚽</div>
          <h1 className="mt-2 text-xl font-bold">AI World Cup 2026</h1>
          <p className="text-sm text-slate-400">Predicción y tracking del Mundial</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Usuario</label>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-400">Contraseña</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
              {error}
            </div>
          )}
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Entrando…" : "Iniciar sesión"}
          </button>
        </form>
      </div>
    </div>
  );
}
