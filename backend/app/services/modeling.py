"""Modelado sobre la base de datos: Elo, predicciones por partido y simulación del torneo.

Cablea el núcleo ML (paquete `ml`) con la persistencia: actualiza el Elo de los
equipos, genera la predicción Dixon-Coles de cada partido y corre el Monte Carlo
condicionado por los resultados ya registrados.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

from sqlalchemy.orm import Session

from ml.ingest.historical import get_results
from ml.models.dixon_coles import predict
from ml.models.elo import build_lookup, compute_elo, get_elo
from ml.simulation.monte_carlo import GROUP_LABELS, simulate_tournament

from ..config import settings
from ..models.football import (
    Match,
    Prediction,
    RatingSnapshot,
    SimulationRun,
    Team,
    TeamAdvanceProb,
)

logger = logging.getLogger("wc2026.modeling")

ARTIFACTS_DIR = Path("ml/artifacts")
ARTIFACT_PATHS = {
    "xgboost": ARTIFACTS_DIR / "xgboost.joblib",
    "nn": ARTIFACTS_DIR / "neural_net.pt",
    "bayesian": ARTIFACTS_DIR / "bayesian.joblib",
}

# Estado actual por equipo (Elo + forma) cacheado para alimentar los modelos ML/DL.
_state_cache: dict | None = None


def _current_state() -> dict:
    global _state_cache
    if _state_cache is None:
        from ml.features.build_features import compute_current_state

        _state_cache = compute_current_state(get_results())
    return _state_cache


def available_models() -> list[str]:
    """Modelos utilizables: 'elo' siempre; los demás si existe su artefacto."""
    models = ["elo"]
    models += [name for name, path in ARTIFACT_PATHS.items() if path.exists()]
    return models


def train_ml_models(force_download: bool = False, include_bayes: bool = False) -> list[str]:
    """Entrena XGBoost, la red (y el bayesiano si include_bayes) y guarda los artefactos."""
    from ml.features.build_features import build_features

    feat = build_features(get_results(force=force_download))
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    trained: list[str] = []

    try:
        from ml.models.xgboost_model import XGBoostGoalModel

        XGBoostGoalModel().fit(feat).save(ARTIFACT_PATHS["xgboost"])
        trained.append("xgboost")
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo entrenar XGBoost: %s", exc)

    try:
        from ml.models.neural_net import NeuralGoalModel

        NeuralGoalModel().fit(feat).save(str(ARTIFACT_PATHS["nn"]))
        trained.append("nn")
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo entrenar la red neuronal: %s", exc)

    if include_bayes:
        try:
            from ml.models.bayesian import BayesianGoalModel

            BayesianGoalModel().fit(feat).save(ARTIFACT_PATHS["bayesian"])
            trained.append("bayesian")
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo entrenar el modelo bayesiano: %s", exc)

    global _state_cache
    _state_cache = None  # refrescar estado tras reentrenar
    return trained


def _goal_model_for(model_name: str):
    """Devuelve un goal_model(teams)->L para el modelo dado, o None para Elo."""
    if model_name in ("elo", "dixon_coles"):
        return None
    from ml.models.grid import make_goal_model

    if model_name == "xgboost":
        from ml.models.xgboost_model import XGBoostGoalModel

        model = XGBoostGoalModel.load(ARTIFACT_PATHS["xgboost"])
    elif model_name == "nn":
        from ml.models.neural_net import NeuralGoalModel

        model = NeuralGoalModel.load(str(ARTIFACT_PATHS["nn"]))
    elif model_name == "bayesian":
        from ml.models.bayesian import BayesianGoalModel

        model = BayesianGoalModel.load(ARTIFACT_PATHS["bayesian"])
    else:
        raise ValueError(f"Modelo desconocido: {model_name}")
    return make_goal_model(model, _current_state())


def update_team_elos(db: Session, lookup: dict[str, float]) -> None:
    """Asigna a cada equipo su Elo actual y guarda una foto en RatingSnapshot."""
    for team in db.query(Team).all():
        team.elo = get_elo(lookup, team.name)
        db.add(RatingSnapshot(team_id=team.id, elo=team.elo))
    db.commit()


def _groups_and_elos(db: Session) -> tuple[dict[str, list[str]], dict[str, float]]:
    groups: dict[str, list[str]] = {}
    elos: dict[str, float] = {}
    for team in db.query(Team).all():
        if team.group_label:
            groups.setdefault(team.group_label, []).append(team.name)
        elos[team.name] = team.elo
    ordered = {g: groups[g] for g in GROUP_LABELS if g in groups}
    return ordered, elos


def _predict_with_ml_model(model_obj, home_name: str, away_name: str, is_neutral: bool):
    """Usa un modelo ML que expone predict_lambdas para generar una MatchPrediction."""
    import numpy as np

    from ml.models.dixon_coles import MatchPrediction, outcome_probs, score_matrix
    from ml.models.grid import pair_feature_frame

    state = _current_state()
    teams = [home_name, away_name]
    df = pair_feature_frame(teams, state)
    lh_arr, la_arr = model_obj.predict_lambdas(df)
    lh = float(np.asarray(lh_arr).reshape(2, 2)[0, 1])
    la = float(np.asarray(la_arr).reshape(2, 2)[0, 1])
    if not is_neutral:
        from ml.models.dixon_coles import HFA_ELO
        lh = float(np.clip(lh + HFA_ELO * 0.01, 0.3, 6.0))
    mat = score_matrix(lh, la)
    p_home, p_draw, p_away = outcome_probs(mat)
    sh = math.floor(lh + 0.3)  # <0.7→abajo, ≥0.7→arriba
    sa = math.floor(la + 0.3)
    return MatchPrediction(
        p_home=p_home, p_draw=p_draw, p_away=p_away,
        exp_home_goals=lh, exp_away_goals=la,
        top_scoreline=f"{sh}-{sa}", score_matrix=mat,
    )


def _load_ml_model(model_name: str):
    """Carga el artefacto ML para un modelo dado. Devuelve None si no existe."""
    path = ARTIFACT_PATHS.get(model_name)
    if path is None or not path.exists():
        return None
    try:
        if model_name == "xgboost":
            from ml.models.xgboost_model import XGBoostGoalModel
            return XGBoostGoalModel.load(path)
        if model_name == "nn":
            from ml.models.neural_net import NeuralGoalModel
            return NeuralGoalModel.load(str(path))
        if model_name == "bayesian":
            from ml.models.bayesian import BayesianGoalModel
            return BayesianGoalModel.load(path)
    except Exception as exc:
        logger.warning("No se pudo cargar el modelo %s: %s", model_name, exc)
    return None


def generate_predictions(db: Session, model_name: str = "dixon_coles") -> int:
    """(Re)genera predicciones por partido para un modelo específico.

    Borra solo las filas de ese modelo antes de regenerar, preservando las de otros.
    """
    db.query(Prediction).filter(Prediction.model_name == model_name).delete()

    teams = {t.id: t for t in db.query(Team).all()}
    matches = (
        db.query(Match)
        .filter(Match.home_team_id.isnot(None), Match.away_team_id.isnot(None))
        .all()
    )

    # Para modelos ML cargamos el artefacto una vez
    ml_obj = None if model_name in ("dixon_coles", "elo") else _load_ml_model(model_name)
    if model_name not in ("dixon_coles", "elo") and ml_obj is None:
        logger.warning("generate_predictions: artefacto no disponible para '%s'", model_name)
        return 0

    count = 0
    for m in matches:
        home, away = teams[m.home_team_id], teams[m.away_team_id]
        try:
            if ml_obj is not None:
                p = _predict_with_ml_model(ml_obj, home.name, away.name, m.is_neutral)
            else:
                p = predict(home.elo, away.elo, is_neutral=m.is_neutral)
        except Exception as exc:
            logger.warning("Predicción fallida match %s (%s): %s", m.id, model_name, exc)
            continue

        db.add(
            Prediction(
                match_id=m.id,
                model_name=model_name,
                p_home=p.p_home,
                p_draw=p.p_draw,
                p_away=p.p_away,
                exp_home_goals=p.exp_home_goals,
                exp_away_goals=p.exp_away_goals,
                top_scoreline=p.top_scoreline,
            )
        )
        count += 1
    db.commit()
    return count


def generate_all_predictions(db: Session) -> None:
    """Regenera predicciones por partido para dixon_coles y todos los modelos ML disponibles."""
    generate_predictions(db, "dixon_coles")
    for name in available_models():
        if name != "elo":  # elo usa las mismas lambdas que dixon_coles
            generate_predictions(db, name)


def collect_fixed_results(db: Session) -> dict[tuple[str, str], tuple[int, int]]:
    """Resultados de grupo ya jugados, para condicionar la simulación."""
    names = {t.id: t.name for t in db.query(Team).all()}
    fixed: dict[tuple[str, str], tuple[int, int]] = {}
    finished = (
        db.query(Match)
        .filter(
            Match.stage == "group",
            Match.status == "finished",
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
        )
        .all()
    )
    for m in finished:
        if m.home_team_id in names and m.away_team_id in names:
            fixed[(names[m.home_team_id], names[m.away_team_id])] = (
                int(m.home_score),
                int(m.away_score),
            )
    return fixed


def run_simulation(
    db: Session, runs: int | None = None, notes: str = "", model_name: str = "elo"
) -> SimulationRun:
    """Corre el Monte Carlo (condicionado por resultados) con el modelo elegido."""
    runs = runs or settings.monte_carlo_runs
    groups, elos = _groups_and_elos(db)
    fixed = collect_fixed_results(db)
    goal_model = _goal_model_for(model_name)
    if goal_model is None:
        result = simulate_tournament(groups, elos, runs=runs, fixed_results=fixed)
    else:
        result = simulate_tournament(groups, runs=runs, fixed_results=fixed, goal_model=goal_model)

    run = SimulationRun(runs=runs, model_name=model_name, notes=notes)
    db.add(run)
    db.flush()

    name_to_id = {t.name: t.id for t in db.query(Team).all()}
    for name, tp in result.probs.items():
        db.add(
            TeamAdvanceProb(
                run_id=run.id,
                team_id=name_to_id[name],
                p_group_winner=tp.p_group_winner,
                p_group_runner_up=tp.p_group_runner_up,
                p_advance=tp.p_advance,
                p_r16=tp.p_r16,
                p_qf=tp.p_qf,
                p_sf=tp.p_sf,
                p_final=tp.p_final,
                p_winner=tp.p_winner,
            )
        )
    db.commit()
    return run


def bayesian_team_strength(db: Session) -> list[dict] | None:
    """Fuerza ataque/defensa (medias posteriores + IC 95%) por equipo del Mundial.

    Devuelve None si el modelo bayesiano no está entrenado.
    """
    path = ARTIFACT_PATHS["bayesian"]
    if not path.exists():
        return None
    from ml.models.bayesian import BayesianGoalModel
    from ml.models.elo import fold_name

    strengths = BayesianGoalModel.load(path).team_strength()
    out = []
    for team in db.query(Team).all():
        s = strengths.get(fold_name(team.name))
        if s is None:
            continue
        att, att_std = s["att"], s["att_std"]
        dfn, def_std = s["def"], s["def_std"]
        overall = att + dfn
        overall_std = (att_std**2 + def_std**2) ** 0.5
        out.append(
            {
                "team": team.name,
                "display_name": team.display_name,
                "code": team.code,
                "confederation": team.confederation,
                "group_label": team.group_label,
                "att": att,
                "att_std": att_std,
                "defense": dfn,
                "def_std": def_std,
                "overall": overall,
                "overall_lo": overall - 1.96 * overall_std,
                "overall_hi": overall + 1.96 * overall_std,
            }
        )
    out.sort(key=lambda x: x["overall"], reverse=True)
    return out


def recalc_all(db: Session, notes: str = "") -> None:
    """Recalcula predicciones y simulaciones de todos los modelos disponibles."""
    generate_all_predictions(db)
    for name in available_models():
        run_simulation(db, notes=notes, model_name=name)


def full_train(
    db: Session,
    force_download: bool = False,
    runs: int | None = None,
    with_ml: bool = False,
    with_bayes: bool = False,
) -> SimulationRun:
    """Pipeline: histórico -> Elo -> predicciones -> simulación (y modelos ML si with_ml)."""
    df = get_results(force=force_download)
    ratings = compute_elo(df)
    lookup = build_lookup(ratings)
    update_team_elos(db, lookup)
    generate_all_predictions(db)
    elo_run = run_simulation(db, runs=runs, notes="entrenamiento", model_name="elo")

    if with_ml or with_bayes:
        for name in train_ml_models(force_download=False, include_bayes=with_bayes):
            generate_predictions(db, name)
            run_simulation(db, runs=runs, notes=f"entrenamiento {name}", model_name=name)
    return elo_run
