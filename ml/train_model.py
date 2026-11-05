"""Group-held-out evaluation; classifier selection uses training fleets only."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FEATURES = ["speed", "battery", "motor_temp", "vibration", "motor_current", "obstacle_distance"]
LABELS = ["NORMAL", "WARNING", "CRITICAL"]
SEED = 606


def make_candidates() -> dict:
    return {
        "LogisticRegression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1500, random_state=SEED)),
        ]),
        "RandomForest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("classifier", RandomForestClassifier(n_estimators=120, max_depth=14, min_samples_leaf=3, class_weight="balanced_subsample", random_state=SEED, n_jobs=1)),
        ]),
    }


def plots(df, report, predictions, y_test, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = ["#158575", "#c68717", "#d4505a"]
    fig, ax = plt.subplots(figsize=(7, 3.8), layout="constrained")
    counts = df.status.value_counts().reindex(LABELS, fill_value=0)
    bars = ax.bar(LABELS, counts, color=colors)
    ax.bar_label(bars, padding=3)
    ax.set(ylabel="Muestras", title=f"Distribución real de las clases ({df.fleet_id.nunique()} flotas sintéticas)")
    ax.set_ylim(0, counts.max() * 1.18)
    fig.savefig(destination / "class_distribution.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.8), layout="constrained")
    ConfusionMatrixDisplay(confusion_matrix(y_test, predictions, labels=LABELS), display_labels=LABELS).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set(title=f"Flotas de prueba: {report['selected_model']}", xlabel="Clase predicha", ylabel="Clase real")
    fig.savefig(destination / "confusion_matrix.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3.8), layout="constrained")
    names = list(report["models"])
    cv = [report["models"][name]["cv_macro_f1_mean"] for name in names]
    scores = [report["models"][name]["test_macro_f1"] for name in names]
    x = np.arange(len(names))
    ax.bar(x - .18, cv, .36, label="Validación por grupos", color="#278d83")
    ax.bar(x + .18, scores, .36, label="Prueba (flotas reservadas)", color="#325776")
    ax.axhline(report["baseline_macro_f1"], color="#bd5d46", linestyle="--", label="Clase mayoritaria")
    ax.set(xticks=x, xticklabels=names, ylim=(0, 1), ylabel="F1 macro", title="Comparación de clasificadores")
    ax.legend(loc="lower right")
    fig.savefig(destination / "model_comparison.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(10, 6), layout="constrained")
    for feature, ax in zip(FEATURES, axes.flat):
        for label, color in zip(LABELS, colors):
            ax.hist(df.loc[df.status == label, feature], bins=32, alpha=.45, density=True, color=color, label=label)
        ax.set(title=feature, ylabel="Densidad")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("EDA: distribución de las seis variables por condición")
    fig.savefig(destination / "feature_distributions.png", dpi=180)
    plt.close(fig)


def train(data: Path, output: Path, reports: Path) -> dict:
    if not data.is_file():
        raise SystemExit("Generar primero: python ml/generate_fleets.py")
    df = pd.read_csv(data)
    required = set(FEATURES + ["status", "fleet_id"])
    if not required.issubset(df.columns):
        raise ValueError("Se requiere fleet_id. Usar ml/generate_fleets.py; el generador original no incluye grupos.")
    if set(df.status) != set(LABELS) or df.fleet_id.nunique() < 8:
        raise ValueError("Se requieren tres clases y al menos ocho flotas")
    if not np.isfinite(df[FEATURES].to_numpy()).all():
        raise ValueError("Dataset con variables no finitas o ausentes")
    X, y, groups = df[FEATURES].to_numpy(), df.status.to_numpy(), df.fleet_id.to_numpy()
    train_index, test_index = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=SEED).split(X, y, groups))
    train_groups, test_groups = sorted(set(groups[train_index])), sorted(set(groups[test_index]))
    assert set(train_groups).isdisjoint(test_groups)
    X_train, X_test, y_train, y_test = X[train_index], X[test_index], y[train_index], y[test_index]
    if set(y_train) != set(LABELS) or set(y_test) != set(LABELS):
        raise ValueError("Alguna partición carece de una clase")
    candidates = make_candidates()
    results = {}
    with threadpool_limits(limits=1):
        for name, candidate in candidates.items():
            cv = cross_val_score(candidate, X_train, y_train, groups=groups[train_index], cv=GroupKFold(n_splits=4), scoring="f1_macro", n_jobs=1)
            results[name] = {"cv_macro_f1_mean": float(cv.mean()), "cv_macro_f1_std": float(cv.std()), "cv_folds": cv.tolist()}
            print(name, "CV F1 macro =", round(cv.mean(), 5), flush=True)
        # Selection is fixed before examining the held-out test labels or scores.
        best = max(results, key=lambda name: results[name]["cv_macro_f1_mean"])
        if results[best]["cv_macro_f1_mean"] - results["LogisticRegression"]["cv_macro_f1_mean"] <= .005:
            best = "LogisticRegression"
        fitted = {}
        for name, candidate in candidates.items():
            fitted[name] = clone(candidate).fit(X_train, y_train)
            pred = fitted[name].predict(X_test)
            start = perf_counter()
            for row in X_test[:200]:
                fitted[name].predict_proba(row.reshape(1, -1))
            results[name].update(
                test_macro_f1=float(f1_score(y_test, pred, average="macro")),
                confusion_matrix=confusion_matrix(y_test, pred, labels=LABELS).tolist(),
                classification_report=classification_report(y_test, pred, labels=LABELS, output_dict=True, zero_division=0),
                mean_single_inference_ms=(perf_counter() - start) * 1000 / min(200, len(X_test)),
            )
    baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
    baseline_score = float(f1_score(y_test, baseline.predict(X_test), average="macro"))
    sha = hashlib.sha256(data.read_bytes()).hexdigest()
    version = f"v1-{'lr' if best == 'LogisticRegression' else 'rf'}-{sha[:10]}"
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": version, "selected_model": best, "seed": SEED,
        "dataset_sha256": sha, "samples": len(df), "fleets": df.fleet_id.nunique(),
        "class_distribution": {label: int((y == label).sum()) for label in LABELS},
        "missing_values": df[sorted(required)].isna().sum().astype(int).to_dict(),
        "feature_summary": df[FEATURES].describe().to_dict(),
        "train_samples": len(train_index), "test_samples": len(test_index),
        "train_fleets": train_groups, "test_fleets": test_groups, "overlapping_fleets": [],
        "train_class_distribution": {label: int((y_train == label).sum()) for label in LABELS},
        "test_class_distribution": {label: int((y_test == label).sum()) for label in LABELS},
        "features": FEATURES, "labels": LABELS, "models": results,
        "test_macro_f1": results[best]["test_macro_f1"], "baseline_macro_f1": baseline_score,
        "selection_rule": "Highest 4-fold GroupKFold macro F1 on training fleets; prefer logistic if within 0.005. Test fleets are used only after selection.",
        "python_version": platform.python_version(), "sklearn_version": sklearn.__version__,
        "limitations": "Datos sintéticos del simulador docente. No acreditan desempeño en robots reales. Confidence es probabilidad estimada, sin calibración independiente.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline": fitted[best], "features": FEATURES, "model_version": version, "selected_model": best,
        "evaluation": {"test_macro_f1": report["test_macro_f1"], "baseline_macro_f1": baseline_score, "test_fleets": len(test_groups)},
    }, output, compress=3)
    (output.parent / "metadata.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    df[FEATURES].describe().to_csv(reports / "feature_summary.csv")
    df.groupby("status")[FEATURES].mean().reindex(LABELS).to_csv(reports / "feature_means_by_class.csv")
    plots(df, report, fitted[best].predict(X_test), y_test, reports)
    table = "\n".join(f"| {name} | {r['cv_macro_f1_mean']:.4f} ± {r['cv_macro_f1_std']:.4f} | {r['test_macro_f1']:.4f} | {r['mean_single_inference_ms']:.3f} |" for name, r in results.items())
    reason = ("La regresión logística alcanza el mejor resultado o queda a menos de 0,005 del mejor F1 de validación. Su coste de inferencia y tamaño son menores, adecuados para el plan gratuito." if best == "LogisticRegression" else "Random Forest obtiene una ventaja de F1 macro superior a 0,005 en validación por grupos y representa relaciones no lineales. Se limita la profundidad y se usa un solo hilo por predicción para contener memoria y concurrencia.")
    markdown = f"""# Evidencia del modelo

Dataset sintético: **{len(df):,} muestras y {df.fleet_id.nunique()} flotas**, semilla {SEED}.
Generado con `ml/generate_fleets.py` a partir de `simulator/core.py`, conservado sin cambios.
SHA-256: `{sha}`.

## EDA y variables

Clases: {report['class_distribution']}. Ausentes: {sum(report['missing_values'].values())}.
Se registran los conteos observados, sin asumir que CRITICAL sea la clase minoritaria.
Se usan velocidad, batería, temperatura, vibración, corriente y distancia al obstáculo.
Los histogramas muestran que temperatura y vibración separan mejor las condiciones;
velocidad, batería y distancia presentan más solapamiento. Esto describe asociación, no causalidad.
Se excluyen fleet_id, robot_id, timestamp, x e y para evitar memorizar identidad o trayectoria.

![Distribución de clases](class_distribution.png)
![Distribuciones de variables](feature_distributions.png)

## Separación y elección

GroupShuffleSplit reserva 25% de las flotas: {len(train_groups)} flotas / {len(train_index):,} muestras de entrenamiento;
{len(test_groups)} flotas / {len(test_index):,} muestras de prueba. Intersección de grupos: cero.
El entrenamiento usa GroupKFold de cuatro particiones. Imputación y escalado se ajustan dentro de cada pipeline y partición.
La selección se fija con F1 macro de validación; si la diferencia es menor o igual a 0,005 se prefiere la regresión logística.
La prueba se consulta después de fijar esa elección. El artefacto conserva el ajuste exclusivo a las flotas de entrenamiento.

| Clasificador | F1 macro validación (media ± DE) | F1 macro prueba | Inferencia local media (ms) |
|---|---:|---:|---:|
{table}

Línea base de clase mayoritaria: **{baseline_score:.4f}** F1 macro.
Seleccionado: **{best}**. {reason}
La latencia anterior mide el pipeline, no la red ni el arranque en frío del PaaS.

![Comparación](model_comparison.png)
![Matriz de confusión](confusion_matrix.png)

## Reproducibilidad y alcance

Versión `{version}`; scikit-learn {sklearn.__version__}; Python {platform.python_version()}.
`models/model.joblib` contiene imputación, escalado cuando corresponde, clasificador, variables y versión.
Listas completas de flotas, clasificación por clase, matrices de ambos modelos y estadísticas en `evaluation.json`.

{report['limitations']}
La evaluación pública y la flota del docente son verificaciones distintas de esta prueba reservada.
"""
    (reports / "MODEL_REPORT.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"selected": best, "test_macro_f1": report["test_macro_f1"], "baseline": baseline_score, "model_version": version}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/training.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "models/model.joblib")
    parser.add_argument("--reports", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    train(args.data, args.output, args.reports)
