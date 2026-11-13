"""
Reproducible training pipeline for the crop recommendation model.

Run it with `python manage.py train_model` (see recommendations/management/
commands/train_model.py). Every stage below is recorded in model_card.json
next to the saved model, so the deployed model can always be traced back to
the exact data, preprocessing, split, settings and scores that produced it.

Pipeline
--------
1. Load      Kaggle benchmark (22 crops) + synthetic Uganda crops (16 crops).
2. Validate  required columns, missing values, negatives, duplicates, class balance.
3. Harmonise rainfall: the Kaggle rows are on a monthly scale (20-300 mm) while
             the synthetic rows came from annual FAO EcoCrop ranges (200-2,600 mm),
             so rainfall alone could tell the two sources apart. Synthetic
             rainfall is divided by 12 to put both on the monthly scale.
4. Split     stratified 80/20 train/test, fixed seed.
5. Compare   8 candidate models with stratified k-fold CV on the training set
             (optionally grid-searched first), plus held-out test scores,
             accuracy split by data origin, and corrected paired t-tests.
   Select    by default the model with the best CV macro F1 is deployed.
6. Evaluate  the deployed model: per-class report, confusion matrix,
             permutation feature importance.
7. Save      model + encoder + feature names, model card, comparison tables,
             the harmonised training dataset, and suitability ranges derived
             from that same dataset (so the UI can't contradict the model).

The deployed model is the one fitted on the training split, so the reported
test scores describe exactly the artifact the app serves.
"""

import hashlib
import io
import json
import math
import platform
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import sklearn
import xgboost
from scipy import stats
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, cross_validate, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from .features import FEATURE_NAMES, RAINFALL_MONTHS

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "datasets"
MODEL_DIR = ML_DIR / "model"

KAGGLE_FILE = DATA_DIR / "Crop_Recommendation_kaggle_dataset.csv"
SYNTHETIC_FILE = DATA_DIR / "Uganda_New_Crops_Synthetic_Only.csv"
SUITABILITY_FILE_NAME = "Uganda_Crop_Suitability_Ranges.csv"
LABEL = "Crop"

ORIGIN_KAGGLE = "Kaggle"
ORIGIN_SYNTHETIC = "Synthetic (Uganda-added)"

# (feature, display min column, display max column, round-to step) for the
# suitability ranges shown to farmers. Rainfall is converted back to annual mm.
SUITABILITY_COLUMNS = [
    ("Nitrogen", "N_min", "N_max", 5),
    ("Phosphorus", "P_min", "P_max", 5),
    ("Potassium", "K_min", "K_max", 5),
    ("Temperature", "Temp_min", "Temp_max", 1),
    ("Humidity", "Hum_min", "Hum_max", 5),
    ("pH_Value", "pH_min", "pH_max", 0.1),
    ("Rainfall", "Rain_min", "Rain_max", 50),
]


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _origin_separability(df, cv):
    """How well rainfall ALONE separates Kaggle rows from synthetic rows
    (one-split decision tree, CV accuracy). ~0.58 is chance for this data."""
    is_synthetic = (df["origin"] == ORIGIN_SYNTHETIC).astype(int)
    return float(cross_val_score(DecisionTreeClassifier(max_depth=1), df[["Rainfall"]], is_synthetic, cv=cv).mean())


def load_and_validate(log):
    sources = []
    for path, origin in [(KAGGLE_FILE, ORIGIN_KAGGLE), (SYNTHETIC_FILE, ORIGIN_SYNTHETIC)]:
        frame = pd.read_csv(path)
        frame.columns = [c.strip() for c in frame.columns]
        missing = [c for c in FEATURE_NAMES + [LABEL] if c not in frame.columns]
        if missing:
            raise ValueError(f"{path.name} is missing columns {missing}")
        frame = frame[FEATURE_NAMES + [LABEL]].copy()
        frame[LABEL] = frame[LABEL].astype(str).str.strip()
        frame["origin"] = origin
        sources.append((path, frame))
        log(f"  {path.name}: {len(frame)} rows, {frame[LABEL].nunique()} crops")

    df = pd.concat([frame for _, frame in sources], ignore_index=True)

    overlap = set(sources[0][1][LABEL]) & set(sources[1][1][LABEL])
    if overlap:
        raise ValueError(f"Crops present in both sources: {sorted(overlap)}")
    if df[FEATURE_NAMES].isna().any().any():
        raise ValueError("Missing feature values found - clean the data first.")
    if (df[FEATURE_NAMES] < 0).any().any():
        raise ValueError("Negative feature values found.")
    duplicates = int(df.duplicated(subset=FEATURE_NAMES + [LABEL]).sum())
    if duplicates:
        log(f"  Dropping {duplicates} duplicate rows")
        df = df.drop_duplicates(subset=FEATURE_NAMES + [LABEL]).reset_index(drop=True)

    counts = df[LABEL].value_counts()
    report = {
        "sources": [
            {
                "file": path.name,
                "origin": frame["origin"].iloc[0],
                "rows": len(frame),
                "crops": int(frame[LABEL].nunique()),
                "sha256": _sha256(path),
            }
            for path, frame in sources
        ],
        "rows": len(df),
        "crops": int(df[LABEL].nunique()),
        "rows_per_crop": {"min": int(counts.min()), "max": int(counts.max())},
        "duplicates_dropped": duplicates,
        "missing_values": 0,
    }
    log(f"  Combined: {report['rows']} rows, {report['crops']} crops, "
        f"{report['rows_per_crop']['min']}-{report['rows_per_crop']['max']} rows per crop, "
        f"{duplicates} duplicates dropped")
    return df, report


def harmonise_rainfall(df, cv, log):
    def ranges(frame):
        return {
            origin: [round(float(group["Rainfall"].min()), 1), round(float(group["Rainfall"].max()), 1)]
            for origin, group in frame.groupby("origin")
        }

    before_ranges, before_sep = ranges(df), _origin_separability(df, cv)
    df = df.copy()
    synthetic = df["origin"] == ORIGIN_SYNTHETIC
    df.loc[synthetic, "Rainfall"] = (df.loc[synthetic, "Rainfall"] / RAINFALL_MONTHS).round(2)
    after_ranges, after_sep = ranges(df), _origin_separability(df, cv)

    log(f"  Rainfall ranges before: {before_ranges}")
    log(f"  Rainfall ranges after:  {after_ranges}")
    log(f"  Rainfall alone separates the two sources: {before_sep:.3f} before -> {after_sep:.3f} after")
    return df, {
        "rule": f"Synthetic rows' annual rainfall (mm/year) divided by {RAINFALL_MONTHS} to match the Kaggle monthly scale (mm/month).",
        "app_input": f"Farmers enter annual rainfall; ml/features.py divides by {RAINFALL_MONTHS} before prediction.",
        "rainfall_range_by_origin_before": before_ranges,
        "rainfall_range_by_origin_after": after_ranges,
        "origin_separability_by_rainfall_before": round(before_sep, 4),
        "origin_separability_by_rainfall_after": round(after_sep, 4),
        "origin_separability_chance_level": round(float(max(synthetic.mean(), 1 - synthetic.mean())), 4),
    }


def candidate_models(seed):
    """{name: (estimator, grid used only when tuning)}."""
    def scaled(clf):
        return Pipeline([("scaler", StandardScaler()), ("clf", clf)])

    return {
        "XGBoost": (
            XGBClassifier(objective="multi:softprob", eval_metric="mlogloss", tree_method="hist",
                          random_state=seed, n_jobs=-1),
            {"n_estimators": [200, 400], "max_depth": [4, 6], "learning_rate": [0.05, 0.1]},
        ),
        "Random Forest": (
            RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=-1),
            {"n_estimators": [200, 400], "max_depth": [None, 20]},
        ),
        "Gradient Boosting": (
            GradientBoostingClassifier(random_state=seed),
            {"n_estimators": [100, 200], "learning_rate": [0.05, 0.1], "max_depth": [3]},
        ),
        "Decision Tree": (
            DecisionTreeClassifier(random_state=seed),
            {"max_depth": [None, 10, 20], "min_samples_leaf": [1, 3]},
        ),
        "Naive Bayes": (GaussianNB(), {"var_smoothing": [1e-11, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6]}),
        "KNN": (
            scaled(KNeighborsClassifier()),
            {"clf__n_neighbors": [3, 5, 7, 11], "clf__weights": ["uniform", "distance"]},
        ),
        "SVM (RBF)": (
            scaled(SVC(kernel="rbf", probability=True, random_state=seed)),
            {"clf__C": [1, 10, 100], "clf__gamma": ["scale", 0.1]},
        ),
        "Logistic Regression": (
            scaled(LogisticRegression(max_iter=2000, random_state=seed)),
            {"clf__C": [0.1, 1, 10]},
        ),
    }


# How the app's "why this crop" panel can explain each model (see ml/explainer.py).
EXPLANATION_METHOD = {
    "XGBoost": "Exact SHAP (TreeExplainer)",
    "Random Forest": "Exact SHAP (TreeExplainer)",
    "Gradient Boosting": "Exact SHAP (TreeExplainer)",
    "Decision Tree": "Exact SHAP (TreeExplainer)",
    "Naive Bayes": "Exact per-feature log-likelihood contributions",
}


def corrected_paired_ttest(scores_a, scores_b, n_train, folds):
    """Nadeau & Bengio corrected resampled t-test on per-fold CV scores.
    A plain paired t-test is too optimistic because CV training sets overlap."""
    diff = np.asarray(scores_a) - np.asarray(scores_b)
    var = diff.var(ddof=1)
    if var == 0:
        return float(diff.mean()), 1.0 if diff.mean() == 0 else 0.0
    n_test_fold = n_train / folds
    correction = 1 / folds + n_test_fold / (n_train - n_test_fold)
    t = diff.mean() / math.sqrt(correction * var)
    return float(diff.mean()), float(2 * stats.t.sf(abs(t), df=folds - 1))


def _round_out(value, step, up):
    result = (math.ceil if up else math.floor)(value / step) * step
    return round(result, 1) if step < 1 else int(result)


def build_suitability_ranges(df, categories):
    rows = []
    for crop, group in df.groupby(LABEL):
        row = {"Crop": crop}
        for feature, min_col, max_col, step in SUITABILITY_COLUMNS:
            low, high = group[feature].min(), group[feature].max()
            if feature == "Rainfall":
                low, high = low * RAINFALL_MONTHS, high * RAINFALL_MONTHS
            row[min_col] = _round_out(low, step, up=False)
            row[max_col] = _round_out(high, step, up=True)
        row["Category"] = categories.get(crop, "")
        rows.append(row)
    order = {crop: i for i, crop in enumerate(categories)}
    rows.sort(key=lambda r: order.get(r["Crop"], len(order)))
    columns = ["Crop"] + [c for _, lo, hi, _ in SUITABILITY_COLUMNS for c in (lo, hi)] + ["Category"]
    return pd.DataFrame(rows, columns=columns)


def train(output_dir=MODEL_DIR, seed=42, test_size=0.2, folds=10, tune=True, deploy="best",
          models=None, log=print):
    """deploy="best" selects the model with the highest CV macro F1 (ties broken
    by test F1); pass a model name to override that choice."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)

    log("1-2. Loading and validating data")
    df, data_report = load_and_validate(log)

    log("3. Harmonising rainfall")
    df, harmonisation = harmonise_rainfall(df, cv, log)

    log("4. Splitting")
    encoder = LabelEncoder()
    y = encoder.fit_transform(df[LABEL])
    X = df[FEATURE_NAMES].astype(float)
    origin = df["origin"].to_numpy()
    X_tr, X_te, y_tr, y_te, _, o_te = train_test_split(
        X, y, origin, test_size=test_size, stratify=y, random_state=seed
    )
    log(f"  Train {len(X_tr)} / test {len(X_te)} (stratified by crop, seed {seed})")

    candidates = candidate_models(seed)
    if deploy != "best" and deploy not in candidates:
        raise ValueError(f"Unknown deploy model '{deploy}'. Choose 'best' or one of {list(candidates)}")
    if models:
        unknown = [m for m in models if m not in candidates]
        if unknown:
            raise ValueError(f"Unknown model(s) {unknown}. Choose from {list(candidates)}")
        candidates = {name: candidates[name] for name in candidates if name in models or name == deploy}
        if len(candidates) < 2:
            raise ValueError("Compare at least two models.")

    log(f"5. Comparing {len(candidates)} models ({folds}-fold CV on the training set"
        f"{', grid-searched first' if tune else ''})")
    rows, fitted, fold_scores = [], {}, {}
    scoring = {"accuracy": "accuracy", "f1": "f1_macro"}
    for name, (estimator, grid) in candidates.items():
        best_params = {}
        if tune and grid:
            search = GridSearchCV(estimator, grid, cv=5, scoring="f1_macro", n_jobs=-1)
            search.fit(X_tr, y_tr)
            estimator, best_params = search.best_estimator_, search.best_params_

        cv_result = cross_validate(estimator, X_tr, y_tr, cv=cv, scoring=scoring, n_jobs=-1)
        fold_scores[name] = cv_result["test_accuracy"]

        t0 = time.perf_counter()
        estimator.fit(X_tr, y_tr)
        train_seconds = time.perf_counter() - t0
        t0 = time.perf_counter()
        pred = estimator.predict(X_te)
        inference_ms = (time.perf_counter() - t0) / len(X_te) * 1000
        buffer = io.BytesIO()
        joblib.dump(estimator, buffer)

        row = {
            "model": name,
            "cv_accuracy_mean": round(float(cv_result["test_accuracy"].mean()), 4),
            "cv_accuracy_std": round(float(cv_result["test_accuracy"].std()), 4),
            "cv_f1_macro_mean": round(float(cv_result["test_f1"].mean()), 4),
            "test_accuracy": round(accuracy_score(y_te, pred), 4),
            "test_precision_macro": round(precision_score(y_te, pred, average="macro", zero_division=0), 4),
            "test_recall_macro": round(recall_score(y_te, pred, average="macro", zero_division=0), 4),
            "test_f1_macro": round(f1_score(y_te, pred, average="macro", zero_division=0), 4),
            "test_accuracy_kaggle": round(accuracy_score(y_te[o_te == ORIGIN_KAGGLE], pred[o_te == ORIGIN_KAGGLE]), 4),
            "test_accuracy_synthetic": round(accuracy_score(y_te[o_te == ORIGIN_SYNTHETIC], pred[o_te == ORIGIN_SYNTHETIC]), 4),
            "train_seconds": round(train_seconds, 3),
            "inference_ms_per_sample": round(inference_ms, 4),
            "model_size_kb": round(len(buffer.getvalue()) / 1024, 1),
            "explanation_method": EXPLANATION_METHOD.get(name, "None in the app"),
            "best_params": json.dumps(best_params, default=str) if best_params else "",
        }
        rows.append(row)
        fitted[name] = (estimator, pred, best_params)
        log(f"  {name:20s} CV acc {row['cv_accuracy_mean']:.4f} ± {row['cv_accuracy_std']:.4f} | "
            f"test acc {row['test_accuracy']:.4f} (Kaggle {row['test_accuracy_kaggle']:.3f}, "
            f"synthetic {row['test_accuracy_synthetic']:.3f}) | F1 {row['test_f1_macro']:.4f}")

    comparison = pd.DataFrame(rows).sort_values(["cv_f1_macro_mean", "test_f1_macro"], ascending=False)
    comparison.insert(0, "rank", range(1, len(comparison) + 1))
    selection_rule = f"Highest {folds}-fold CV macro F1 on the training split (ties broken by test macro F1)"
    if deploy == "best":
        deploy = comparison.iloc[0]["model"]
        log(f"  Selected {deploy} ({selection_rule.lower()})")
    else:
        selection_rule = f"Manually chosen with --deploy (best by CV macro F1 was {comparison.iloc[0]['model']})"

    significance = []
    for other in fold_scores:
        if other == deploy:
            continue
        diff, p = corrected_paired_ttest(fold_scores[deploy], fold_scores[other], len(X_tr), folds)
        significance.append({
            "deployed": deploy,
            "compared_with": other,
            "mean_cv_accuracy_diff": round(diff, 4),
            "p_value": round(p, 4),
            "verdict": "No significant difference" if p >= 0.05 else (f"{deploy} better" if diff > 0 else f"{other} better"),
        })
    significantly_better = [s["compared_with"] for s in significance if s["verdict"] == f"{s['compared_with']} better"]
    if significantly_better:
        log(f"  NOTE: significantly better than {deploy} on CV (p < 0.05): {', '.join(significantly_better)}")

    log(f"6. Evaluating deployed model: {deploy}")
    model, pred, best_params = fitted[deploy]
    per_class = pd.DataFrame(classification_report(
        y_te, pred, target_names=encoder.classes_, output_dict=True, zero_division=0
    )).T.round(4)
    matrix = pd.DataFrame(confusion_matrix(y_te, pred), index=encoder.classes_, columns=encoder.classes_)
    # Permutation importance works for every model type: the drop in test
    # accuracy when one feature's values are shuffled.
    permuted = permutation_importance(model, X_te, y_te, scoring="accuracy", n_repeats=10, random_state=seed, n_jobs=-1)
    importance = {
        feature: round(float(value), 4)
        for feature, value in sorted(zip(FEATURE_NAMES, permuted.importances_mean), key=lambda fv: -fv[1])
    }
    weakest = per_class.loc[encoder.classes_].sort_values("f1-score").head(5)["f1-score"].to_dict()
    deployed_row = comparison.set_index("model").loc[deploy]

    log("7. Saving artifacts")
    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    joblib.dump(model, output_dir / "crop_model.pkl")
    joblib.dump(encoder, output_dir / "crop_encoder.pkl")
    joblib.dump(FEATURE_NAMES, output_dir / "feature_names.pkl")
    comparison.to_csv(output_dir / "model_comparison.csv", index=False)
    pd.DataFrame(significance).to_csv(output_dir / "significance_tests.csv", index=False)
    per_class.to_csv(output_dir / "classification_report.csv")
    matrix.to_csv(output_dir / "confusion_matrix.csv")
    df.to_csv(output_dir / "training_dataset_harmonised.csv", index=False)

    existing_suitability = DATA_DIR / SUITABILITY_FILE_NAME
    categories = dict(pd.read_csv(existing_suitability)[["Crop", "Category"]].itertuples(index=False))
    suitability_path = existing_suitability if output_dir == MODEL_DIR else output_dir / SUITABILITY_FILE_NAME
    build_suitability_ranges(df, categories).to_csv(suitability_path, index=False)

    card = {
        "version": version,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "algorithm": deploy,
        "selection_rule": selection_rule,
        "explanation_method": EXPLANATION_METHOD.get(deploy, "None in the app"),
        "hyperparameters": best_params or "library defaults",
        "features": FEATURE_NAMES,
        "classes": list(encoder.classes_),
        "data": data_report,
        "preprocessing": {
            "rainfall_harmonisation": harmonisation,
            "scaling": "None for the deployed tree model (scale-invariant); StandardScaler inside the KNN, SVM and Logistic Regression pipelines only.",
            "label_encoding": "sklearn LabelEncoder (alphabetical crop order)",
        },
        "split": {
            "method": "Stratified train/test split by crop",
            "test_size": test_size,
            "train_rows": len(X_tr),
            "test_rows": len(X_te),
            "seed": seed,
            "cv_folds": folds,
            "tuned": tune,
            "tuning": "GridSearchCV, 5-fold, scoring = macro F1, on the training split only" if tune else "none",
            "deployed_model_fit_on": "training split (so the test scores below describe exactly the deployed model)",
        },
        "test_metrics": {
            "accuracy": float(deployed_row["test_accuracy"]),
            "precision_macro": float(deployed_row["test_precision_macro"]),
            "recall_macro": float(deployed_row["test_recall_macro"]),
            "f1_macro": float(deployed_row["test_f1_macro"]),
            "accuracy_kaggle_rows": float(deployed_row["test_accuracy_kaggle"]),
            "accuracy_synthetic_rows": float(deployed_row["test_accuracy_synthetic"]),
        },
        "cv_metrics": {
            "accuracy_mean": float(deployed_row["cv_accuracy_mean"]),
            "accuracy_std": float(deployed_row["cv_accuracy_std"]),
            "f1_macro_mean": float(deployed_row["cv_f1_macro_mean"]),
        },
        "weakest_crops_f1": {crop: round(float(score), 4) for crop, score in weakest.items()},
        "feature_importance": importance,
        "feature_importance_method": "Permutation importance on the test set (mean drop in accuracy over 10 shuffles)",
        "comparison": comparison.to_dict(orient="records"),
        "significance_tests": significance,
        "significantly_better_than_deployed": significantly_better,
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "shap": shap.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "artifacts": [
            "crop_model.pkl", "crop_encoder.pkl", "feature_names.pkl", "model_comparison.csv",
            "significance_tests.csv", "classification_report.csv", "confusion_matrix.csv",
            "training_dataset_harmonised.csv", f"{SUITABILITY_FILE_NAME} ({suitability_path.parent.name}/)",
        ],
        "duration_seconds": round(time.perf_counter() - started, 1),
    }
    (output_dir / "model_card.json").write_text(json.dumps(card, indent=2, default=str))
    log(f"  Saved model version {version} to {output_dir}")
    return card
