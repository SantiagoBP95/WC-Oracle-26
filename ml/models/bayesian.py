"""Modelo bayesiano jerárquico de goles (PyMC), estilo Baio-Blangiardo / Dixon-Coles.

Cada equipo tiene una fuerza de ataque (att) y de defensa (def) con priors jerárquicos:
    log λ_local  = intercepto + ventaja_local·(no neutral) + att[local] − def[visitante]
    log λ_visit. = intercepto + att[visitante] − def[local]

Se ajusta con ADVI (variacional, rápido) sobre datos recientes; se guardan las medias
posteriores (att/def) y sus desviaciones (intervalos de credibilidad). En predicción NO
hace falta PyMC: solo aritmética con los parámetros guardados.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .dixon_coles import MAX_LAMBDA, MIN_LAMBDA, probs_from_lambdas
from .elo import fold_name


class BayesianGoalModel:
    def __init__(self):
        self.intercept = float(np.log(1.35))
        self.home_adv = 0.25
        self.att: dict[str, float] = {}
        self.defn: dict[str, float] = {}
        self.att_std: dict[str, float] = {}
        self.def_std: dict[str, float] = {}

    def fit(
        self,
        feat: pd.DataFrame,
        window_years: float = 3.0,
        advi_iters: int = 15000,
        draws: int = 500,
        seed: int = 42,
    ) -> "BayesianGoalModel":
        import pymc as pm

        # Ventana relativa a la fecha más reciente (sirve también en backtest).
        cutoff = feat["date"].max() - pd.Timedelta(days=int(window_years * 365))
        d = feat[feat["date"] >= cutoff].reset_index(drop=True)
        teams = sorted(set(d["home_team"]) | set(d["away_team"]))
        tidx = {t: i for i, t in enumerate(teams)}
        hi = d["home_team"].map(tidx).to_numpy()
        ai = d["away_team"].map(tidx).to_numpy()
        neutral = d["neutral"].to_numpy().astype(float)
        hg = d["home_goals"].to_numpy()
        ag = d["away_goals"].to_numpy()
        n = len(teams)

        with pm.Model():
            sd_att = pm.HalfNormal("sd_att", 1.0)
            sd_def = pm.HalfNormal("sd_def", 1.0)
            att_raw = pm.Normal("att_raw", 0.0, sd_att, shape=n)
            def_raw = pm.Normal("def_raw", 0.0, sd_def, shape=n)
            att = pm.Deterministic("att", att_raw - att_raw.mean())  # identificabilidad
            defn = pm.Deterministic("def", def_raw - def_raw.mean())
            intercept = pm.Normal("intercept", float(np.log(1.35)), 0.3)
            home_adv = pm.Normal("home_adv", 0.25, 0.2)

            log_lh = intercept + (1.0 - neutral) * home_adv + att[hi] - defn[ai]
            log_la = intercept + att[ai] - defn[hi]
            pm.Poisson("obs_h", mu=pm.math.exp(log_lh), observed=hg)
            pm.Poisson("obs_a", mu=pm.math.exp(log_la), observed=ag)

            approx = pm.fit(advi_iters, method="advi", random_seed=seed, progressbar=False)
            idata = approx.sample(draws)

        post = idata.posterior
        att_m = post["att"].mean(("chain", "draw")).to_numpy()
        att_s = post["att"].std(("chain", "draw")).to_numpy()
        def_m = post["def"].mean(("chain", "draw")).to_numpy()
        def_s = post["def"].std(("chain", "draw")).to_numpy()
        self.intercept = float(post["intercept"].mean())
        self.home_adv = float(post["home_adv"].mean())
        self.att = {fold_name(t): float(att_m[i]) for t, i in tidx.items()}
        self.defn = {fold_name(t): float(def_m[i]) for t, i in tidx.items()}
        self.att_std = {fold_name(t): float(att_s[i]) for t, i in tidx.items()}
        self.def_std = {fold_name(t): float(def_s[i]) for t, i in tidx.items()}
        return self

    def _vec(self, names: np.ndarray, table: dict[str, float]) -> np.ndarray:
        return np.array([table.get(fold_name(n), 0.0) for n in names])

    def predict_lambdas(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        h, a = df["home_team"].to_numpy(), df["away_team"].to_numpy()
        neutral = df["neutral"].to_numpy()
        ah, dh = self._vec(h, self.att), self._vec(h, self.defn)
        aa, da = self._vec(a, self.att), self._vec(a, self.defn)
        adv = np.where(neutral == 1, 0.0, self.home_adv)
        lh = np.clip(np.exp(self.intercept + adv + ah - da), MIN_LAMBDA, MAX_LAMBDA)
        la = np.clip(np.exp(self.intercept + aa - dh), MIN_LAMBDA, MAX_LAMBDA)
        return lh, la

    def predict_probs(self, df: pd.DataFrame) -> np.ndarray:
        lh, la = self.predict_lambdas(df)
        return np.array([probs_from_lambdas(float(x), float(y)) for x, y in zip(lh, la)])

    def team_strength(self) -> dict[str, dict[str, float]]:
        """Fuerza ataque/defensa por equipo con su desviación (intervalo de credibilidad)."""
        return {
            t: {
                "att": self.att[t],
                "att_std": self.att_std.get(t, 0.0),
                "def": self.defn[t],
                "def_std": self.def_std.get(t, 0.0),
            }
            for t in self.att
        }

    def save(self, path: str | Path) -> None:
        joblib.dump(
            {
                "intercept": self.intercept,
                "home_adv": self.home_adv,
                "att": self.att,
                "defn": self.defn,
                "att_std": self.att_std,
                "def_std": self.def_std,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "BayesianGoalModel":
        d = joblib.load(path)
        m = cls()
        m.intercept, m.home_adv = d["intercept"], d["home_adv"]
        m.att, m.defn = d["att"], d["defn"]
        m.att_std, m.def_std = d["att_std"], d["def_std"]
        return m
