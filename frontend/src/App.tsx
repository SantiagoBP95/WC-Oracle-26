import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";

// Code-splitting por ruta: cada página (y sus dependencias pesadas, p. ej.
// recharts en Dashboard/Comparador) se descarga solo cuando se navega a ella.
const Admin = lazy(() => import("./pages/Admin"));
const BetBuilder = lazy(() => import("./pages/BetBuilder"));
const Bracket = lazy(() => import("./pages/Bracket"));
const Comparador = lazy(() => import("./pages/Comparador"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Groups = lazy(() => import("./pages/Groups"));
const Guia = lazy(() => import("./pages/Guia"));
const Rendimiento = lazy(() => import("./pages/Rendimiento"));
const Upgrade = lazy(() => import("./pages/Upgrade"));

function PageFallback() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "4rem", color: "#9ca3af" }}>
      Cargando…
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/upgrade" element={<Upgrade />} />
          <Route path="/grupos" element={<Groups />} />
          <Route path="/bracket" element={<Bracket />} />
          <Route path="/partidos" element={<Navigate to="/bracket" replace />} />
          <Route path="/comparador" element={<Comparador />} />
          <Route path="/bets" element={<BetBuilder />} />
          <Route path="/rendimiento" element={<Rendimiento />} />
          <Route path="/guia" element={<Guia />} />
          <Route path="/admin" element={<Admin />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
