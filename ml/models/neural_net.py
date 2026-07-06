"""Red neuronal (PyTorch): embeddings de equipos + MLP con salida Poisson de goles.

Cada equipo aprende un vector latente (fuerza/estilo); el MLP combina ambos embeddings
con las features de contexto y predice goles esperados (λ) de local y visitante.
Las probabilidades 1X2 salen de la misma máquina Dixon-Coles que el resto de modelos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from .dixon_coles import MAX_LAMBDA, MIN_LAMBDA, probs_from_lambdas
from .elo import fold_name

NUMERIC = [
    "neutral",
    "elo_diff",
    "form_home_pts",
    "form_away_pts",
    "gf_home",
    "ga_home",
    "gf_away",
    "ga_away",
    "weight",
]


def pick_device():
    """Elige dispositivo: DirectML (AMD/Intel en Windows) > CUDA (NVIDIA) > CPU.

    Para una GPU AMD (p. ej. RX 6750) en Windows, instala `torch-directml` y se usará
    automáticamente. Sin GPU compatible, cae a CPU (suficiente para este modelo).
    """
    try:
        import torch_directml  # type: ignore

        return torch_directml.device()
    except Exception:
        pass
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class _Net(nn.Module):
    def __init__(self, n_teams: int, emb_dim: int, n_numeric: int, hidden: int):
        super().__init__()
        self.emb = nn.Embedding(n_teams, emb_dim)
        self.mlp = nn.Sequential(
            nn.Linear(2 * emb_dim + n_numeric, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 2),
        )

    def forward(self, home_idx, away_idx, numeric):
        x = torch.cat([self.emb(home_idx), self.emb(away_idx), numeric], dim=1)
        return torch.nn.functional.softplus(self.mlp(x)) + 1e-3  # λ > 0


class NeuralGoalModel:
    def __init__(self, emb_dim=16, hidden=64, epochs=12, lr=1e-3, batch=1024, seed=42, device=None):
        self.emb_dim, self.hidden = emb_dim, hidden
        self.epochs, self.lr, self.batch, self.seed = epochs, lr, batch, seed
        self.device = device or pick_device()
        self.vocab: dict[str, int] = {}
        self.mu = self.sd = self.net = None

    def _ids(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        h = df["home_team"].map(lambda t: self.vocab.get(fold_name(t), 0)).to_numpy()
        a = df["away_team"].map(lambda t: self.vocab.get(fold_name(t), 0)).to_numpy()
        return h, a

    def _numeric(self, df: pd.DataFrame) -> np.ndarray:
        return (df[NUMERIC].to_numpy(dtype=float) - self.mu) / self.sd

    def fit(self, train_df: pd.DataFrame) -> "NeuralGoalModel":
        torch.manual_seed(self.seed)
        teams = pd.unique(pd.concat([train_df["home_team"], train_df["away_team"]]))
        self.vocab = {fold_name(t): i + 1 for i, t in enumerate(teams)}  # 0 = desconocido
        Xn = train_df[NUMERIC].to_numpy(dtype=float)
        self.mu, self.sd = Xn.mean(0), Xn.std(0) + 1e-6
        self.net = _Net(len(self.vocab) + 1, self.emb_dim, len(NUMERIC), self.hidden).to(self.device)

        h = torch.tensor(self._ids(train_df)[0], dtype=torch.long, device=self.device)
        a = torch.tensor(self._ids(train_df)[1], dtype=torch.long, device=self.device)
        num = torch.tensor(self._numeric(train_df), dtype=torch.float32, device=self.device)
        y = torch.tensor(
            np.stack([train_df["home_goals"].to_numpy(float), train_df["away_goals"].to_numpy(float)], 1),
            dtype=torch.float32,
            device=self.device,
        )

        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        loss_fn = nn.PoissonNLLLoss(log_input=False, full=False)
        n = len(y)
        self.net.train()
        for _ in range(self.epochs):
            perm = torch.randperm(n).to(self.device)
            for i in range(0, n, self.batch):
                idx = perm[i : i + self.batch]
                opt.zero_grad()
                loss = loss_fn(self.net(h[idx], a[idx], num[idx]), y[idx])
                loss.backward()
                opt.step()
        return self

    @torch.no_grad()
    def predict_lambdas(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        self.net.eval()
        h, a = self._ids(df)
        lam = self.net(
            torch.tensor(h, dtype=torch.long, device=self.device),
            torch.tensor(a, dtype=torch.long, device=self.device),
            torch.tensor(self._numeric(df), dtype=torch.float32, device=self.device),
        ).cpu().numpy()
        lh = np.clip(lam[:, 0], MIN_LAMBDA, MAX_LAMBDA)
        la = np.clip(lam[:, 1], MIN_LAMBDA, MAX_LAMBDA)
        return lh, la

    def predict_probs(self, df: pd.DataFrame) -> np.ndarray:
        lh, la = self.predict_lambdas(df)
        return np.array([probs_from_lambdas(float(x), float(y)) for x, y in zip(lh, la)])

    def save(self, path: str) -> None:
        torch.save(
            {
                "state": self.net.state_dict(),
                "vocab": self.vocab,
                "mu": self.mu,
                "sd": self.sd,
                "emb_dim": self.emb_dim,
                "hidden": self.hidden,
            },
            path,
        )

    @classmethod
    def load(cls, path: str, device=None) -> "NeuralGoalModel":
        data = torch.load(path, map_location="cpu", weights_only=False)
        model = cls(emb_dim=data["emb_dim"], hidden=data["hidden"], device=device)
        model.vocab, model.mu, model.sd = data["vocab"], data["mu"], data["sd"]
        model.net = _Net(len(model.vocab) + 1, model.emb_dim, len(NUMERIC), model.hidden).to(model.device)
        model.net.load_state_dict(data["state"])
        model.net.eval()
        return model
