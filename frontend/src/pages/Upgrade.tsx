import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const PRO_FEATURES = [
  { icon: "🏟️", label: "Grupos", desc: "Tabla de clasificación en vivo con probabilidades de avance para los 12 grupos" },
  { icon: "⚽", label: "Bracket completo", desc: "Camino al título interactivo con probabilidades por ronda para los 48 equipos" },
  { icon: "🎯", label: "Bet Builder", desc: "Probabilidades de tiros a puerta por jugador convocado con cuotas implícitas" },
  { icon: "📈", label: "Rendimiento del modelo", desc: "Seguimiento del acierto de las predicciones en tiempo real" },
  { icon: "⚖️", label: "Comparador de modelos", desc: "Elo, XGBoost, Red Neuronal y Bayesiano comparados con métricas de calibración" },
  { icon: "🔄", label: "Recálculo en vivo", desc: "Probabilidades recalculadas automáticamente tras cada partido disputado" },
];

export default function Upgrade() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      {/* Badge Preview */}
      <div className="mb-6 flex items-center gap-3">
        <span className="rounded-full bg-amber-500/20 px-3 py-1 text-xs font-semibold text-amber-400 ring-1 ring-amber-500/40">
          PLAN PREVIEW
        </span>
        <span className="text-sm text-slate-400">
          Conectado como <span className="font-medium text-slate-200">{user?.username}</span>
        </span>
      </div>

      {/* Hero */}
      <h1 className="mb-2 text-3xl font-bold leading-tight">
        Desbloquea el análisis completo
      </h1>
      <p className="mb-8 text-slate-400">
        Con tu plan actual ves el Dashboard con la predicción del próximo partido.
        Hazte con el plan <span className="font-semibold text-pitch">Pro</span> para acceder
        a todas las funcionalidades del predictor.
      </p>

      {/* Feature grid */}
      <div className="mb-8 grid gap-3 sm:grid-cols-2">
        {PRO_FEATURES.map((f) => (
          <div
            key={f.label}
            className="flex gap-3 rounded-xl border border-line bg-panel p-4"
          >
            <span className="text-2xl leading-none">{f.icon}</span>
            <div>
              <div className="mb-0.5 text-sm font-semibold">{f.label}</div>
              <div className="text-xs leading-snug text-slate-400">{f.desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="rounded-2xl border border-pitch/30 bg-pitch/10 p-6 text-center">
        <div className="mb-1 text-lg font-bold text-pitch">Plan Pro</div>
        <p className="mb-4 text-sm text-slate-400">
          Contacta al administrador para activar tu acceso completo.
        </p>
        <a
          href="mailto:wcoracle.team@gmail.com?subject=Solicitud%20Plan%20Pro%20WC%20Oracle%202026"
          className="inline-block rounded-lg bg-pitch px-6 py-2.5 text-sm font-semibold text-ink transition hover:bg-pitch/80"
        >
          Solicitar Plan Pro
        </a>
        <p className="mt-3 text-xs text-slate-500">wcoracle.team@gmail.com</p>
      </div>

      {/* Back to dashboard */}
      <button
        onClick={() => navigate("/")}
        className="mt-6 w-full py-2 text-sm text-slate-500 hover:text-slate-300 transition"
      >
        ← Volver al Dashboard
      </button>
    </div>
  );
}
