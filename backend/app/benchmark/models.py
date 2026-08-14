from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


class BenchmarkClassifier(ABC):
    model_id: str
    family: str

    @abstractmethod
    def fit(
        self,
        x_train_features: np.ndarray,
        x_train_raw: np.ndarray,
        y_train: np.ndarray,
        x_validation_features: np.ndarray,
        x_validation_raw: np.ndarray,
        y_validation: np.ndarray,
    ) -> None: ...

    @abstractmethod
    def predict_proba(self, x_features: np.ndarray, x_raw: np.ndarray) -> np.ndarray: ...

    def save(self, path: Path) -> int | None:
        return None


class CalibratedFeatureClassifier(BenchmarkClassifier):
    def __init__(self, model_id: str, family: str, estimator: Any) -> None:
        self.model_id = model_id
        self.family = family
        self.base_estimator = estimator
        self.estimator: Any | None = None

    def fit(
        self,
        x_train_features: np.ndarray,
        x_train_raw: np.ndarray,
        y_train: np.ndarray,
        x_validation_features: np.ndarray,
        x_validation_raw: np.ndarray,
        y_validation: np.ndarray,
    ) -> None:
        del x_train_raw, x_validation_raw
        self.base_estimator.fit(x_train_features, y_train)
        _, counts = np.unique(y_validation, return_counts=True)
        calibration_folds = max(2, min(5, int(np.min(counts))))
        calibrator = CalibratedClassifierCV(
            estimator=FrozenEstimator(self.base_estimator),
            method="sigmoid",
            cv=calibration_folds,
            ensemble=False,
        )
        calibrator.fit(x_validation_features, y_validation)
        self.estimator = calibrator

    def predict_proba(self, x_features: np.ndarray, x_raw: np.ndarray) -> np.ndarray:
        del x_raw
        if self.estimator is None:
            raise RuntimeError("Model is not fitted")
        return np.asarray(self.estimator.predict_proba(x_features), dtype=np.float64)

    def save(self, path: Path) -> int | None:
        if self.estimator is None:
            raise RuntimeError("Model is not fitted")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.estimator, path)
        return path.stat().st_size


def build_feature_models(seed: int) -> list[BenchmarkClassifier]:
    return [
        CalibratedFeatureClassifier(
            "dsp-calibrated-rf-v0.2",
            "DSP + validation-calibrated random forest",
            RandomForestClassifier(
                n_estimators=180,
                max_depth=None,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            ),
        ),
        CalibratedFeatureClassifier(
            "dsp-calibrated-et-v0.2",
            "DSP + validation-calibrated extra trees",
            ExtraTreesClassifier(
                n_estimators=200,
                min_samples_leaf=2,
                class_weight="balanced",
                random_state=seed + 1,
                n_jobs=-1,
            ),
        ),
        CalibratedFeatureClassifier(
            "dsp-calibrated-hgb-v0.2",
            "DSP + validation-calibrated histogram gradient boosting",
            HistGradientBoostingClassifier(
                max_iter=180,
                learning_rate=0.08,
                max_leaf_nodes=31,
                l2_regularization=0.2,
                random_state=seed + 2,
            ),
        ),
        CalibratedFeatureClassifier(
            "dsp-calibrated-logreg-v0.2",
            "DSP + validation-calibrated multinomial logistic regression",
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            C=2.0,
                            max_iter=4_000,
                            class_weight="balanced",
                            random_state=seed,
                        ),
                    ),
                ]
            ),
        ),
        CalibratedFeatureClassifier(
            "dsp-calibrated-rbf-svm-v0.2",
            "DSP + validation-calibrated RBF SVM",
            Pipeline(
                [
                    ("scaler", StandardScaler()),
                    (
                        "svc",
                        SVC(
                            C=8.0,
                            gamma="scale",
                            kernel="rbf",
                            probability=False,
                            class_weight="balanced",
                            random_state=seed,
                        ),
                    ),
                ]
            ),
        ),
    ]


@dataclass(slots=True)
class _TorchBundle:
    torch: Any
    nn: Any
    functional: Any


def _torch_bundle() -> _TorchBundle:
    import torch
    from torch import nn
    from torch.nn import functional

    return _TorchBundle(torch=torch, nn=nn, functional=functional)


class TinyResNet1DClassifier(BenchmarkClassifier):
    model_id = "tiny-resnet1d-v0.2"
    family = "Compact 1D residual CNN"

    def __init__(self, classes: int, *, epochs: int = 8, seed: int = 42) -> None:
        self.classes = classes
        self.epochs = epochs
        self.seed = seed
        self.bundle = _torch_bundle()
        self.model = self._build_model()
        self.mean = 0.0
        self.std = 1.0
        self.temperature = 1.0

    def _build_model(self):
        torch = self.bundle.torch
        nn = self.bundle.nn

        class ResidualBlock(nn.Module):
            def __init__(self, channels: int, dilation: int) -> None:
                super().__init__()
                padding = dilation * 3
                self.net = nn.Sequential(
                    nn.Conv1d(
                        channels,
                        channels,
                        kernel_size=7,
                        padding=padding,
                        dilation=dilation,
                        bias=False,
                    ),
                    nn.BatchNorm1d(channels),
                    nn.GELU(),
                    nn.Conv1d(channels, channels, kernel_size=5, padding=2, bias=False),
                    nn.BatchNorm1d(channels),
                )
                self.act = nn.GELU()

            def forward(self, x):
                return self.act(x + self.net(x))

        class Net(nn.Module):
            def __init__(self, classes: int) -> None:
                super().__init__()
                self.stem = nn.Sequential(
                    nn.Conv1d(1, 32, kernel_size=15, stride=2, padding=7, bias=False),
                    nn.BatchNorm1d(32),
                    nn.GELU(),
                    nn.MaxPool1d(4),
                )
                self.blocks = nn.Sequential(
                    ResidualBlock(32, 1), ResidualBlock(32, 2), ResidualBlock(32, 4)
                )
                self.head = nn.Sequential(
                    nn.AdaptiveAvgPool1d(1),
                    nn.Flatten(),
                    nn.Linear(32, 48),
                    nn.GELU(),
                    nn.Dropout(0.1),
                    nn.Linear(48, classes),
                )

            def forward(self, x):
                return self.head(self.blocks(self.stem(x)))

        torch.manual_seed(self.seed)
        return Net(self.classes)

    def _normalize(self, x_raw: np.ndarray) -> np.ndarray:
        return ((x_raw - self.mean) / max(self.std, 1e-6)).astype(np.float32)

    def fit(
        self,
        x_train_features: np.ndarray,
        x_train_raw: np.ndarray,
        y_train: np.ndarray,
        x_validation_features: np.ndarray,
        x_validation_raw: np.ndarray,
        y_validation: np.ndarray,
    ) -> None:
        del x_train_features, x_validation_features
        torch = self.bundle.torch
        self.mean = float(np.mean(x_train_raw))
        self.std = float(np.std(x_train_raw) + 1e-6)
        x = torch.from_numpy(self._normalize(x_train_raw)[:, None, :])
        target = torch.from_numpy(y_train.astype(np.int64))
        validation_x = torch.from_numpy(self._normalize(x_validation_raw)[:, None, :])
        validation_target = torch.from_numpy(y_validation.astype(np.int64))
        dataset = torch.utils.data.TensorDataset(x, target)
        generator = torch.Generator().manual_seed(self.seed)
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=64, shuffle=True, generator=generator
        )
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=1.8e-3, weight_decay=1e-3)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=max(1, self.epochs)
        )
        criterion = self.bundle.nn.CrossEntropyLoss(label_smoothing=0.04)
        best_state = None
        best_loss = float("inf")
        for _ in range(self.epochs):
            self.model.train()
            for batch, labels in loader:
                optimizer.zero_grad(set_to_none=True)
                logits = self.model(batch)
                loss = criterion(logits, labels)
                loss.backward()
                self.bundle.nn.utils.clip_grad_norm_(self.model.parameters(), 5.0)
                optimizer.step()
            scheduler.step()
            self.model.eval()
            with torch.inference_mode():
                validation_loss = float(criterion(self.model(validation_x), validation_target))
            if validation_loss < best_loss:
                best_loss = validation_loss
                best_state = {
                    key: value.detach().cpu().clone() for key, value in self.model.state_dict().items()
                }
        if best_state:
            self.model.load_state_dict(best_state)

        self.model.eval()
        with torch.inference_mode():
            logits = self.model(validation_x)
        temperatures = torch.linspace(0.5, 3.0, 51)
        losses = [
            float(self.bundle.functional.cross_entropy(logits / temp, validation_target))
            for temp in temperatures
        ]
        self.temperature = float(temperatures[int(np.argmin(losses))])

    def predict_proba(self, x_features: np.ndarray, x_raw: np.ndarray) -> np.ndarray:
        del x_features
        torch = self.bundle.torch
        x = torch.from_numpy(self._normalize(x_raw)[:, None, :])
        self.model.eval()
        outputs: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, x.shape[0], 128):
                logits = self.model(x[start : start + 128]) / self.temperature
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
                outputs.append(probs)
        return np.concatenate(outputs, axis=0).astype(np.float64)

    def save(self, path: Path) -> int | None:
        torch = self.bundle.torch
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.model.state_dict(),
                "classes": self.classes,
                "mean": self.mean,
                "std": self.std,
                "temperature": self.temperature,
                "seed": self.seed,
            },
            path,
        )
        return path.stat().st_size
