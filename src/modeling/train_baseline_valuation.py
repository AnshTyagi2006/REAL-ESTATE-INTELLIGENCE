from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT
    / "data"
    / "modeling"
    / "valuation_modeling_dataset.csv"
)

OUTPUT_DIR = ROOT / "data" / "models" / "baseline"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FILE = OUTPUT_DIR / "baseline_model.joblib"
METRICS_FILE = OUTPUT_DIR / "model_metrics.json"
PREDICTIONS_FILE = OUTPUT_DIR / "test_predictions.csv"
IMPORTANCE_FILE = OUTPUT_DIR / "feature_importance.csv"


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(INPUT_FILE, low_memory=False)

print("=" * 70)
print("BASELINE REAL ESTATE VALUATION MODEL")
print("=" * 70)

print(f"Dataset rows    : {len(df):,}")
print(f"Dataset columns : {len(df.columns):,}")


# ============================================================
# FEATURES AND TARGET
# ============================================================

FEATURES = [
    "valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "property_type",
    "floor",
    "total_floors",
]

TARGET = "asking_price_inr"
LOG_TARGET = "log_asking_price"


X = df[FEATURES].copy()

# We train on log(price).
y = df[LOG_TARGET].copy()


# ============================================================
# FEATURE TYPES
# ============================================================

NUMERIC_FEATURES = [
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "floor",
    "total_floors",
]

CATEGORICAL_FEATURES = [
    "city",
    "locality",
    "property_type",
]


# ============================================================
# PREPROCESSING
# ============================================================

numeric_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median"),
        )
    ]
)

categorical_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="most_frequent"),
        ),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False,
            ),
        ),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        (
            "numeric",
            numeric_pipeline,
            NUMERIC_FEATURES,
        ),
        (
            "categorical",
            categorical_pipeline,
            CATEGORICAL_FEATURES,
        ),
    ]
)


# ============================================================
# MODEL
# ============================================================

model = RandomForestRegressor(
    n_estimators=300,
    random_state=42,
    n_jobs=-1,
    min_samples_leaf=2,
)


# ============================================================
# COMPLETE PIPELINE
# ============================================================

pipeline = Pipeline(
    steps=[
        (
            "preprocessor",
            preprocessor,
        ),
        (
            "model",
            model,
        ),
    ]
)


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
)

print("\nTRAIN / TEST SPLIT")
print("-" * 70)

print(f"Training records : {len(X_train):,}")
print(f"Testing records  : {len(X_test):,}")


# ============================================================
# TRAIN
# ============================================================

print("\nTraining Random Forest...")

pipeline.fit(
    X_train,
    y_train,
)

print("Training complete.")


# ============================================================
# PREDICTION
# ============================================================

pred_log = pipeline.predict(X_test)

# Convert predictions back from log scale to INR.
pred_price = np.expm1(pred_log)

actual_price = np.expm1(y_test)


# ============================================================
# METRICS
# ============================================================

mae = mean_absolute_error(
    actual_price,
    pred_price,
)

rmse = np.sqrt(
    mean_squared_error(
        actual_price,
        pred_price,
    )
)

r2 = r2_score(
    actual_price,
    pred_price,
)

absolute_percentage_error = (
    np.abs(actual_price - pred_price)
    / actual_price
    * 100
)

median_absolute_percentage_error = np.median(
    absolute_percentage_error
)

mean_absolute_percentage_error = np.mean(
    absolute_percentage_error
)


# ============================================================
# PREDICTION BIAS
# ============================================================

mean_error = np.mean(
    pred_price - actual_price
)

median_error = np.median(
    pred_price - actual_price
)


# ============================================================
# SAVE TEST PREDICTIONS
# ============================================================

test_predictions = X_test.copy()

test_predictions["actual_price_inr"] = actual_price
test_predictions["predicted_price_inr"] = pred_price

test_predictions["absolute_error_inr"] = np.abs(
    actual_price - pred_price
)

test_predictions["absolute_percentage_error"] = (
    absolute_percentage_error
)

test_predictions.to_csv(
    PREDICTIONS_FILE,
    index=False,
)


# ============================================================
# FEATURE IMPORTANCE
# ============================================================

fitted_preprocessor = pipeline.named_steps[
    "preprocessor"
]

fitted_model = pipeline.named_steps[
    "model"
]

feature_names = (
    fitted_preprocessor
    .get_feature_names_out()
)

importance = fitted_model.feature_importances_

feature_importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance": importance,
    }
).sort_values(
    "importance",
    ascending=False,
)

feature_importance.to_csv(
    IMPORTANCE_FILE,
    index=False,
)


# ============================================================
# SAVE MODEL
# ============================================================

joblib.dump(
    pipeline,
    MODEL_FILE,
)


# ============================================================
# SAVE METRICS
# ============================================================

metrics = {
    "dataset": {
        "total_records": int(len(df)),
        "training_records": int(len(X_train)),
        "test_records": int(len(X_test)),
    },

    "target": {
        "original": TARGET,
        "model_target": LOG_TARGET,
    },

    "model": {
        "algorithm": "RandomForestRegressor",
        "n_estimators": 300,
        "min_samples_leaf": 2,
        "random_state": 42,
    },

    "metrics": {
        "mae_inr": float(mae),
        "rmse_inr": float(rmse),
        "r2": float(r2),
        "mean_absolute_percentage_error": float(
            mean_absolute_percentage_error
        ),
        "median_absolute_percentage_error": float(
            median_absolute_percentage_error
        ),
    },

    "prediction_bias": {
        "mean_error_inr": float(mean_error),
        "median_error_inr": float(median_error),
    },

    "features": FEATURES,
}


with open(
    METRICS_FILE,
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        metrics,
        file,
        indent=2,
    )


# ============================================================
# TERMINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("BASELINE MODEL RESULTS")
print("=" * 70)

print(
    f"MAE                         : ₹{mae:,.0f}"
)

print(
    f"RMSE                        : ₹{rmse:,.0f}"
)

print(
    f"R²                          : {r2:.4f}"
)

print(
    f"Mean Absolute % Error       : "
    f"{mean_absolute_percentage_error:.2f}%"
)

print(
    f"Median Absolute % Error     : "
    f"{median_absolute_percentage_error:.2f}%"
)

print(
    f"Mean Prediction Error       : "
    f"₹{mean_error:,.0f}"
)

print("\nTOP FEATURES")
print("-" * 70)

print(
    feature_importance.head(15).to_string(
        index=False
    )
)

print("\nFILES CREATED")
print("-" * 70)

print(MODEL_FILE)
print(METRICS_FILE)
print(PREDICTIONS_FILE)
print(IMPORTANCE_FILE)

print("\nBaseline training complete.")