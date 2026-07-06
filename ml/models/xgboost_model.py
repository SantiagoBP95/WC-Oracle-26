"""Modelo XGBoost: dos regresores Poisson (goles de local y de visitante).

Predice goles esperados (λ) a partir de las features pre-partido; las probabilidades
1X2 salen de la misma máquina Dixon-Coles que el baseline, para una comparación justa.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ..features.build_features import FEATURE_COLUMNS
from .dixon_coles import MAX_LAMBDA, MIN_LAMBDA, probs_from_lambdas

DEFAULT_PARAMS = dict(
    objective="count:poisson",
    n_estimators=400,
    max_depth=4,
    learning_rate=0.04,
    subsample=0.85,
    colsample_bytree=0.85,
    min_child_weight=5.0,
    reg_lambda=1.5,
    n_jobs=-1,
)


class XGBoostGoalModel:
    def __init__(self, **params):
        self.params = {**DEFAULT_PARAMS, **params}
        self.model_home: XGBRegressor | None = None
        self.model_away: XGBRegressor | None = None

    def fit(self, train_df: pd.DataFrame) -> "XGBoostGoalModel":
        X = train_df[FEATURE_COLUMNS].to_numpy(dtype=float)
        self.model_home = XGBRegressor(**self.params).fit(X, train_df["home_goals"].to_numpy())
        self.model_away = XGBRegressor(**self.params).fit(X, train_df["away_goals"].to_numpy())
        return self

    def predict_lambdas(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        X = df[FEATURE_COLUMNS].to_numpy(dtype=float)
        lh = np.clip(self.model_home.predict(X), MIN_LAMBDA, MAX_LAMBDA)
        la = np.clip(self.model_away.predict(X), MIN_LAMBDA, MAX_LAMBDA)
        return lh, la

    def predict_probs(self, df: pd.DataFrame) -> np.ndarray:
        lh, la = self.predict_lambdas(df)
        return np.array([probs_from_lambdas(float(h), float(a)) for h, a in zip(lh, la)])

    def save(self, path: str | Path) -> None:
        joblib.dump({"home": self.model_home, "away": self.model_away}, path)

    @classmethod
    def load(cls, path: str | Path) -> "XGBoostGoalModel":
        data = joblib.load(path)
        model = cls()
        model.model_home, model.model_away = data["home"], data["away"]
        return model
