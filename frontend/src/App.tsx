import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Admin from "./pages/Admin";
import BetBuilder from "./pages/BetBuilder";
import Bracket from "./pages/Bracket";
import Comparador from "./pages/Comparador";
import Dashboard from "./pages/Dashboard";
import Groups from "./pages/Groups";
import Guia from "./pages/Guia";
import Login from "./pages/Login";
import Rendimiento from "./pages/Rendimiento";
import Upgrade from "./pages/Upgrade";

export default function App() {
  return (
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
  );
}
