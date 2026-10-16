from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split

from lightgbm import LGBMRegressor


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
    / "lightgbm"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(DATA_PATH)

print("=" * 70)
print("LIGHTGBM REAL ESTATE VALUATION MODEL")
print("=" * 70)

print(f"Dataset shape: {df.shape}")


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


X = df[features].copy()
y = df[target].copy()


# ============================================================
# 4. CATEGORICAL FEATURES
# ============================================================

categorical_features = [
    "city",
    "locality",
    "property_type",
]

for column in categorical_features:
    X[column] = X[column].astype("category")


# ============================================================
# 5. TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
)


print(f"Training rows : {len(X_train)}")
print(f"Testing rows  : {len(X_test)}")


# ============================================================
# 6. LOG TRANSFORMATION
# ============================================================

y_train_log = np.log1p(y_train)


# ============================================================
# 7. LIGHTGBM MODEL
# ============================================================

model = LGBMRegressor(
    objective="regression",
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=31,
    max_depth=-1,
    min_child_samples=20,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.0,
    reg_lambda=0.0,
    random_state=42,
    n_jobs=-1,
    verbosity=-1,
)


# ============================================================
# 8. TRAIN
# ============================================================

print("\nTraining LightGBM...")

model.fit(
    X_train,
    y_train_log,
    categorical_feature=categorical_features,
)

print("Training completed.")


# ============================================================
# 9. PREDICTION
# ============================================================

predicted_log = model.predict(X_test)

# Convert log-price predictions back to rupees
predicted_price = np.expm1(predicted_log)


# ============================================================
# 10. METRICS
# ============================================================

mae = mean_absolute_error(
    y_test,
    predicted_price
)

rmse = np.sqrt(
    mean_squared_error(
        y_test,
        predicted_price
    )
)

r2 = r2_score(
    y_test,
    predicted_price
)

absolute_percentage_error = (
    np.abs(
        y_test - predicted_price
    )
    / y_test
) * 100

mean_absolute_percentage_error = (
    absolute_percentage_error.mean()
)

median_absolute_percentage_error = (
    np.median(
        absolute_percentage_error
    )
)

mean_prediction_error = (
    predicted_price - y_test
).mean()


# ============================================================
# 11. PRINT RESULTS
# ============================================================

print("\n" + "=" * 70)
print("LIGHTGBM RESULTS")
print("=" * 70)

print(f"MAE                       : ₹{mae:,.0f}")
print(f"RMSE                      : ₹{rmse:,.0f}")
print(f"R²                        : {r2:.4f}")

print(
    f"Mean Absolute % Error     : "
    f"{mean_absolute_percentage_error:.2f}%"
)

print(
    f"Median Absolute % Error   : "
    f"{median_absolute_percentage_error:.2f}%"
)

print(
    f"Mean Prediction Error     : "
    f"₹{mean_prediction_error:,.0f}"
)


# ============================================================
# 12. SAVE MODEL
# ============================================================

model_path = (
    OUTPUT_DIR
    / "lightgbm_model.joblib"
)

joblib.dump(
    model,
    model_path
)


# ============================================================
# 13. SAVE METRICS
# ============================================================

metrics = {
    "model": "LGBMRegressor",
    "algorithm": "LightGBM",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "train_rows": len(X_train),
    "test_rows": len(X_test),
    "mae_inr": float(mae),
    "rmse_inr": float(rmse),
    "r2": float(r2),
    "mean_absolute_percentage_error": float(
        mean_absolute_percentage_error
    ),
    "median_absolute_percentage_error": float(
        median_absolute_percentage_error
    ),
    "mean_prediction_error_inr": float(
        mean_prediction_error
    ),
}

metrics_path = (
    OUTPUT_DIR
    / "model_metrics.json"
)

with open(metrics_path, "w") as f:
    json.dump(
        metrics,
        f,
        indent=4
    )


# ============================================================
# 14. SAVE TEST PREDICTIONS
# ============================================================

predictions = X_test.copy()

# Convert categorical columns back to normal values
for column in categorical_features:
    predictions[column] = (
        predictions[column]
        .astype(str)
    )

predictions["actual_price_inr"] = (
    y_test.values
)

predictions["predicted_price_inr"] = (
    predicted_price
)

predictions["absolute_error_inr"] = (
    np.abs(
        predictions["actual_price_inr"]
        - predictions["predicted_price_inr"]
    )
)

predictions[
    "absolute_percentage_error"
] = (
    predictions["absolute_error_inr"]
    / predictions["actual_price_inr"]
) * 100


predictions_path = (
    OUTPUT_DIR
    / "test_predictions.csv"
)

predictions.to_csv(
    predictions_path,
    index=False
)


# ============================================================
# 15. FEATURE IMPORTANCE
# ============================================================

feature_importance = pd.DataFrame(
    {
        "feature": model.feature_name_,
        "importance": model.feature_importances_,
    }
).sort_values(
    "importance",
    ascending=False
)


feature_importance_path = (
    OUTPUT_DIR
    / "feature_importance.csv"
)

feature_importance.to_csv(
    feature_importance_path,
    index=False
)


# ============================================================
# 16. FINAL OUTPUT
# ============================================================

print("\nFiles saved:")

print(
    f"Model             : {model_path}"
)

print(
    f"Metrics            : {metrics_path}"
)

print(
    f"Predictions        : {predictions_path}"
)

print(
    f"Feature importance : {feature_importance_path}"
)


print("\nTop 15 features:")

print(
    feature_importance
    .head(15)
    .to_string(index=False)
)


print("\n" + "=" * 70)
print("LIGHTGBM MODEL COMPLETE")
print("=" * 70)