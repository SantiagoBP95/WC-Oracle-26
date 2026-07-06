"""Backtesting comparativo: Elo (baseline) vs XGBoost vs Red neuronal.

Entrena cada modelo con el histórico anterior a una fecha de corte y evalúa con los
partidos posteriores (sin fuga temporal). Imprime RPS / log-loss / Brier / accuracy.

Uso (desde la raíz del repo):
    python -m ml.backtest                 # corte por defecto 2022-06-01
    python -m ml.backtest --cutoff 2023-01-01
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from .evaluate import evaluate_probs, format_table, outcomes_from_goals, temporal_split
from .features.build_features import build_features
from .ingest.historical import get_results
from .models.dixon_coles import elo_to_lambdas, probs_from_lambdas


def elo_probs(test_df: pd.DataFrame) -> np.ndarray:
    """Baseline: Elo pre-partido -> Dixon-Coles -> 1X2."""
    out = []
    for r in test_df.itertuples(index=False):
        lh, la = elo_to_lambdas(r.elo_home, r.elo_away, is_neutral=bool(r.neutral))
        out.append(probs_from_lambdas(lh, la))
    return np.array(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest comparativo de modelos 1X2")
    ap.add_argument("--cutoff", default="2022-06-01", help="fecha de corte train/test")
    args = ap.parse_args()

    print("Cargando histórico y construyendo features...")
    df = get_results()
    feat = build_features(df)
    train, test = temporal_split(feat, args.cutoff)
    print(f"  train: {len(train):,}   test (>= {args.cutoff}): {len(test):,}")

    outcomes = outcomes_from_goals(
        test["home_goals"].to_numpy(), test["away_goals"].to_numpy()
    )
    results: dict[str, dict[str, float]] = {}

    print("Baseline Elo -> Dixon-Coles...")
    results["Elo+DixonColes"] = evaluate_probs(elo_probs(test), outcomes)

    print("Entrenando XGBoost (goles Poisson)...")
    from .models.xgboost_model import XGBoostGoalModel

    xgb = XGBoostGoalModel().fit(train)
    results["XGBoost"] = evaluate_probs(xgb.predict_probs(test), outcomes)

    print("Entrenando red neuronal (PyTorch)...")
    from .models.neural_net import NeuralGoalModel

    nn_model = NeuralGoalModel().fit(train)
    results["NeuralNet"] = evaluate_probs(nn_model.predict_probs(test), outcomes)

    print("Entrenando bayesiano (PyMC/ADVI)... (puede tardar 1-2 min)")
    try:
        from .models.bayesian import BayesianGoalModel

        bayes = BayesianGoalModel().fit(train, window_years=2.0, advi_iters=8000)
        results["Bayesiano"] = evaluate_probs(bayes.predict_probs(test), outcomes)
    except Exception as exc:  # noqa: BLE001
        print(f"  (bayesiano omitido: {exc})")
        bayes = None

    print("\n== Backtest (todos los partidos; menor RPS/LogLoss/Brier = mejor) ==")
    print(format_table(results))

    # Subconjunto competitivo (sin amistosos: peso > 20).
    mask = test["weight"].to_numpy() > 20.0
    if int(mask.sum()) > 100:
        sub = test[mask]
        oc = outcomes[mask]
        comp = {
            "Elo+DixonColes": evaluate_probs(elo_probs(sub), oc),
            "XGBoost": evaluate_probs(xgb.predict_probs(sub), oc),
            "NeuralNet": evaluate_probs(nn_model.predict_probs(sub), oc),
        }
        if bayes is not None:
            comp["Bayesiano"] = evaluate_probs(bayes.predict_probs(sub), oc)
        print(f"\n== Solo competitivos (no amistosos, n={int(mask.sum()):,}) ==")
        print(format_table(comp))


if __name__ == "__main__":
    main()
