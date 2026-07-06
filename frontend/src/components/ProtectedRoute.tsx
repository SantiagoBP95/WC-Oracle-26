import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function ProtectedRoute({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="grid h-screen place-items-center text-slate-400">Cargando…</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
