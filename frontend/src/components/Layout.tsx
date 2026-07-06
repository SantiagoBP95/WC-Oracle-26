import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useIsPreview } from "../auth/useIsPreview";
import { ModelProvider, useModel } from "../model/ModelContext";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  anyPerm: string[];
  previewLocked?: boolean; // true = visible pero bloqueado en plan Preview
}

const NAV: NavItem[] = [
  { to: "/",           label: "Dashboard",   icon: "📊", anyPerm: ["view_dashboard"] },
  { to: "/grupos",     label: "Grupos",      icon: "🏟️", anyPerm: ["view_dashboard"], previewLocked: true },
  { to: "/bracket",    label: "Partidos",    icon: "⚽", anyPerm: ["view_dashboard"], previewLocked: true },
  { to: "/bets",       label: "Apuestas",    icon: "🎯", anyPerm: ["view_dashboard"], previewLocked: true },
  { to: "/rendimiento",label: "Rendimiento", icon: "📈", anyPerm: ["view_dashboard"], previewLocked: true },
  { to: "/guia",       label: "Guía",        icon: "📖", anyPerm: ["view_dashboard"], previewLocked: true },
  { to: "/comparador", label: "Comparar",    icon: "⚖️", anyPerm: ["view_models"],    previewLocked: true },
  { to: "/admin",      label: "Admin",       icon: "🛡️", anyPerm: ["manage_users", "manage_profiles"] },
];

function ModelSelector() {
  const { model, setModel, models } = useModel();
  const usable = models.filter((m) => m.available);
  if (usable.length <= 1) return null;
  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      <span className="hidden sm:inline">Modelo</span>
      <select
        className="input w-36 py-1.5 text-xs"
        value={model}
        onChange={(e) => setModel(e.target.value)}
      >
        {usable.map((m) => (
          <option key={m.name} value={m.name}>
            {m.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function Layout() {
  const { user, logout, can } = useAuth();
  const isPreview = useIsPreview();
  const navigate = useNavigate();
  // En preview mostramos todos los ítems (locked incluidos); fuera, filtramos por permiso
  const items = isPreview
    ? NAV.filter((n) => n.anyPerm.some(can) || n.previewLocked)
    : NAV.filter((n) => n.anyPerm.some(can));
  const [menuOpen, setMenuOpen] = useState(false);

  function handleNavClick(item: NavItem, e: React.MouseEvent) {
    if (isPreview && item.previewLocked) {
      e.preventDefault();
      navigate("/upgrade");
    }
  }

  return (
    <ModelProvider>
      <div className="flex min-h-screen flex-col md:flex-row">
        {/* ── Sidebar desktop ── */}
        <aside className="hidden w-56 flex-shrink-0 flex-col border-r border-line bg-panel/60 p-4 md:flex">
          <div className="mb-6 flex items-center gap-2 px-2">
            <span className="text-2xl">⚽</span>
            <div>
              <div className="text-sm font-bold leading-tight">WC Oracle</div>
              <div className="text-xs font-semibold text-pitch">2026</div>
            </div>
          </div>
          <nav className="flex flex-1 flex-col gap-1">
            {items.map((i) => {
              const locked = isPreview && !!i.previewLocked;
              return (
                <NavLink
                  key={i.to}
                  to={locked ? "/upgrade" : i.to}
                  end={i.to === "/"}
                  onClick={(e) => handleNavClick(i, e)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                      locked
                        ? "cursor-pointer opacity-40 hover:opacity-60"
                        : isActive
                        ? "bg-pitch/15 text-pitch"
                        : "text-slate-300 hover:bg-panel2"
                    }`
                  }
                >
                  <span>{i.icon}</span>
                  {i.label}
                  {locked && <span className="ml-auto text-xs text-slate-500">🔒</span>}
                </NavLink>
              );
            })}
          </nav>
          <div className="mt-4 rounded-lg border border-line bg-ink/40 p-3 text-xs text-slate-400">
            Elo → Dixon-Coles → Monte Carlo
          </div>
        </aside>

        {/* ── Columna principal ── */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Header */}
          <header className="flex items-center justify-between border-b border-line bg-panel/40 px-4 py-3">
            {/* móvil: logo + título */}
            <div className="flex items-center gap-2 md:hidden">
              <span className="text-lg">⚽</span>
              <span className="text-sm font-bold text-pitch">WC Oracle</span>
            </div>
            <div className="hidden text-sm text-slate-400 md:block">
              WC Oracle · FIFA World Cup 2026
            </div>

            <div className="flex items-center gap-2">
              <ModelSelector />
              {/* Usuario + salir (desktop) */}
              <div className="hidden items-center gap-3 md:flex">
                <div className="text-right">
                  <div className="text-sm font-medium leading-tight">{user?.username}</div>
                  <div className="text-xs text-slate-400">{user?.profile}</div>
                </div>
                <button onClick={logout} className="btn-ghost px-3 py-1.5 text-xs">
                  Salir
                </button>
              </div>
              {/* Menú hamburguesa (móvil) */}
              <button
                className="btn-ghost px-2 py-1.5 text-base md:hidden"
                onClick={() => setMenuOpen((v) => !v)}
                aria-label="Menú"
              >
                {menuOpen ? "✕" : "☰"}
              </button>
            </div>
          </header>

          {/* Menú desplegable en móvil */}
          {menuOpen && (
            <div className="border-b border-line bg-panel/95 px-4 py-3 md:hidden">
              <div className="mb-3 flex items-center justify-between text-sm">
                <span className="font-medium">{user?.username}</span>
                <span className="text-xs text-slate-400">{user?.profile}</span>
              </div>
              {/* Ítems que no caben en la barra inferior (índice ≥ 5) */}
              {items.slice(5).map((i) => {
                const locked = isPreview && !!i.previewLocked;
                return (
                  <NavLink
                    key={i.to}
                    to={locked ? "/upgrade" : i.to}
                    end={i.to === "/"}
                    onClick={(e) => { handleNavClick(i, e); setMenuOpen(false); }}
                    className={({ isActive }) =>
                      `flex items-center gap-2 rounded-lg px-2 py-2 text-sm mb-1 ${
                        locked ? "opacity-40" : isActive ? "text-pitch font-medium" : "text-slate-300"
                      }`
                    }
                  >
                    <span>{i.icon}</span>{i.label}
                    {locked && <span className="ml-auto text-xs text-slate-500">🔒</span>}
                  </NavLink>
                );
              })}
              <button onClick={logout} className="btn-ghost w-full py-2 text-sm mt-1">
                Cerrar sesión
              </button>
            </div>
          )}

          {/* Contenido */}
          <main className="min-w-0 flex-1 overflow-auto p-3 pb-28 md:p-6 md:pb-10">
            <Outlet />
          </main>

          {/* Disclaimer global — visible en desktop y móvil */}
          <footer className="border-t border-line bg-ink/60 px-4 py-2 text-center text-[10px] leading-snug text-slate-600">
            Aplicación independiente de análisis estadístico · No afiliada ni patrocinada por la FIFA, CONMEBOL, UEFA ni ninguna organización deportiva ·{" "}
            <span className="text-slate-700">Solo uso educativo y de referencia</span>
          </footer>
        </div>

        {/* ── Bottom navigation bar (móvil) ── */}
        <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t border-line bg-panel/95 backdrop-blur-sm md:hidden">
          {items.slice(0, 5).map((i) => {
            const locked = isPreview && !!i.previewLocked;
            return (
              <NavLink
                key={i.to}
                to={locked ? "/upgrade" : i.to}
                end={i.to === "/"}
                className={({ isActive }) =>
                  `flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition ${
                    locked ? "opacity-35 text-slate-400" : isActive ? "text-pitch" : "text-slate-400"
                  }`
                }
                onClick={(e) => { handleNavClick(i, e); setMenuOpen(false); }}
              >
                <span className="text-lg leading-none">{i.icon}</span>
                <span>{i.label}{locked ? " 🔒" : ""}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </ModelProvider>
  );
}
