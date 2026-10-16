from pathlib import Path
import json

import numpy as np
import pandas as pd
import lightgbm as lgb

from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ============================================================
# 1. PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "modeling"
    / "valuation_modeling_dataset.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "models"
    / "lightgbm_tuned"
    / "grouped_validation"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(DATA_PATH)

print("=" * 70)
print("TUNED LIGHTGBM — UNSEEN LOCALITY VALIDATION")
print("=" * 70)

print(f"\nTotal properties: {len(df):,}")


# ============================================================
# 3. FEATURES AND TARGET
# ============================================================

features = [
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

target = "asking_price_inr"

required_columns = [
    "valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    target,
]

missing_columns = [
    col
    for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


# ============================================================
# 4. KEEP THE SAME 7,222-PROPERTY POPULATION
# ============================================================

# Only remove records missing the core fields required
# for modelling and locality grouping.
#
# Optional features such as latitude, longitude, floor,
# total_floors and property_type are allowed to be missing.

model_df = df.dropna(
    subset=required_columns
).copy()

print(
    f"Model-ready properties: "
    f"{len(model_df):,}"
)


# ============================================================
# 5. PREPARE CATEGORICAL FEATURES
# ============================================================

categorical_features = [
    "city",
    "locality",
    "property_type",
]

for col in categorical_features:
    model_df[col] = model_df[col].astype("category")


X = model_df[features].copy()

# Log-transform target
y = np.log1p(
    model_df[target].values
)

# Locality is the grouping variable
groups = model_df["locality"].astype(str)


# ============================================================
# 6. GROUPED TRAIN / TEST SPLIT
# ============================================================

splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.20,
    random_state=42,
)

train_idx, test_idx = next(
    splitter.split(
        X,
        y,
        groups=groups
    )
)

X_train = X.iloc[train_idx].copy()
X_test = X.iloc[test_idx].copy()

y_train = y[train_idx]
y_test = y[test_idx]

train_df = model_df.iloc[train_idx]
test_df = model_df.iloc[test_idx]


# ============================================================
# 7. VERIFY LOCALITY SEPARATION
# ============================================================

train_localities = set(
    train_df["locality"].astype(str)
)

test_localities = set(
    test_df["locality"].astype(str)
)

locality_overlap = (
    train_localities
    .intersection(test_localities)
)

print("\n" + "-" * 70)
print("GROUPED SPLIT")
print("-" * 70)

print(
    f"Training properties : "
    f"{len(X_train):,}"
)

print(
    f"Testing properties  : "
    f"{len(X_test):,}"
)

print(
    f"Training localities : "
    f"{len(train_localities):,}"
)

print(
    f"Testing localities  : "
    f"{len(test_localities):,}"
)

print(
    f"Locality overlap   : "
    f"{len(locality_overlap):,}"
)

if locality_overlap:
    raise ValueError(
        "ERROR: Localities overlap between "
        "training and testing data!"
    )

print(
    "✓ No locality leakage detected."
)


# ============================================================
# 8. TUNED LIGHTGBM
# ============================================================

model = lgb.LGBMRegressor(
    objective="regression",

    # Tuned parameters obtained earlier
    n_estimators=500,
    learning_rate=0.10,
    num_leaves=70,
    min_child_samples=20,
    subsample=0.70,
    colsample_bytree=0.70,

    random_state=42,
    n_jobs=-1,
    verbosity=-1,
)


# ============================================================
# 9. TRAIN
# ============================================================

print("\n" + "-" * 70)
print("TRAINING TUNED LIGHTGBM")
print("-" * 70)

model.fit(
    X_train,
    y_train,
    categorical_feature=categorical_features,
)

print(
    "✓ Model training completed."
)


# ============================================================
# 10. PREDICT
# ============================================================

log_predictions = model.predict(
    X_test
)

# Convert log-price predictions back to INR
predictions = np.expm1(
    log_predictions
)

actual = np.expm1(
    y_test
)


# ============================================================
# 11. METRICS
# ============================================================

mae = mean_absolute_error(
    actual,
    predictions
)

rmse = np.sqrt(
    mean_squared_error(
        actual,
        predictions
    )
)

r2 = r2_score(
    actual,
    predictions
)

absolute_percentage_errors = (
    np.abs(
        actual - predictions
    )
    / np.maximum(actual, 1)
) * 100

mean_absolute_percentage_error = (
    np.mean(
        absolute_percentage_errors
    )
)

median_absolute_percentage_error = (
    np.median(
        absolute_percentage_errors
    )
)

mean_prediction_error = np.mean(
    predictions - actual
)


# ============================================================
# 12. DISPLAY RESULTS
# ============================================================

print("\n" + "=" * 70)
print("UNSEEN-LOCALITY VALIDATION RESULTS")
print("=" * 70)

print(
    f"\nMAE                  : "
    f"₹{mae:,.0f}"
)

print(
    f"RMSE                 : "
    f"₹{rmse:,.0f}"
)

print(
    f"R²                   : "
    f"{r2:.4f}"
)

print(
    f"Mean Absolute % Error: "
    f"{mean_absolute_percentage_error:.2f}%"
)

print(
    f"Median Absolute %    : "
    f"{median_absolute_percentage_error:.2f}%"
)

print(
    f"Mean Prediction Error: "
    f"₹{mean_prediction_error:,.0f}"
)


# ============================================================
# 13. SAVE TEST PREDICTIONS
# ============================================================

prediction_columns = [
    "property_id",
    "listing_id",
    "city",
    "locality",
    "asking_price_inr",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
]

predictions_df = test_df[
    prediction_columns
].copy()

predictions_df[
    "predicted_price_inr"
] = predictions

predictions_df[
    "absolute_error_inr"
] = np.abs(
    predictions_df["asking_price_inr"]
    - predictions_df["predicted_price_inr"]
)

predictions_df[
    "absolute_percentage_error"
] = (
    predictions_df["absolute_error_inr"]
    / np.maximum(
        predictions_df["asking_price_inr"],
        1
    )
) * 100

predictions_df.to_csv(
    OUTPUT_DIR
    / "grouped_test_predictions.csv",
    index=False,
)


# ============================================================
# 14. SAVE METRICS
# ============================================================

metrics = {
    "validation_type":
        "unseen_locality_grouped_validation",

    "total_properties":
        int(len(df)),

    "model_ready_properties":
        int(len(model_df)),

    "training_properties":
        int(len(X_train)),

    "testing_properties":
        int(len(X_test)),

    "training_localities":
        int(len(train_localities)),

    "testing_localities":
        int(len(test_localities)),

    "locality_overlap":
        int(len(locality_overlap)),

    "mae_inr":
        float(mae),

    "rmse_inr":
        float(rmse),

    "r2":
        float(r2),

    "mean_absolute_percentage_error":
        float(
            mean_absolute_percentage_error
        ),

    "median_absolute_percentage_error":
        float(
            median_absolute_percentage_error
        ),

    "mean_prediction_error_inr":
        float(
            mean_prediction_error
        ),

    "hyperparameters": {
        "n_estimators": 500,
        "learning_rate": 0.10,
        "num_leaves": 70,
        "min_child_samples": 20,
        "subsample": 0.70,
        "colsample_bytree": 0.70,
        "random_state": 42,
    },
}

with open(
    OUTPUT_DIR
    / "grouped_validation_metrics.json",
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        metrics,
        f,
        indent=4
    )


# ============================================================
# 15. FINAL OUTPUT
# ============================================================

print("\n" + "-" * 70)
print("OUTPUT FILES")
print("-" * 70)

print(
    "✓ grouped_test_predictions.csv"
)

print(
    "✓ grouped_validation_metrics.json"
)

print(
    "\nEvaluation completed successfully."
)