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
from sklearn.model_selection import (
    train_test_split,
    RandomizedSearchCV,
)

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
    / "lightgbm_tuned"
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
print("LIGHTGBM HYPERPARAMETER TUNING")
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
# 5. TRAIN / FINAL TEST SPLIT
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
# 7. BASE LIGHTGBM MODEL
# ============================================================

base_model = LGBMRegressor(
    objective="regression",
    random_state=42,
    n_jobs=-1,
    verbosity=-1,
)


# ============================================================
# 8. HYPERPARAMETER SEARCH SPACE
# ============================================================

param_distributions = {
    "n_estimators": [
        300,
        500,
        700,
        900,
    ],

    "learning_rate": [
        0.01,
        0.03,
        0.05,
        0.10,
    ],

    "num_leaves": [
        15,
        31,
        50,
        70,
    ],

    "min_child_samples": [
        10,
        20,
        30,
        50,
    ],

    "subsample": [
        0.7,
        0.8,
        0.9,
        1.0,
    ],

    "colsample_bytree": [
        0.7,
        0.8,
        0.9,
        1.0,
    ],
}


# ============================================================
# 9. RANDOMIZED SEARCH
# ============================================================

search = RandomizedSearchCV(
    estimator=base_model,
    param_distributions=param_distributions,
    n_iter=20,
    scoring="neg_mean_absolute_error",
    cv=5,
    random_state=42,
    n_jobs=-1,
    verbose=1,
    refit=True,
)


# ============================================================
# 10. TRAIN / TUNE
# ============================================================

print("\nStarting hyperparameter tuning...")

search.fit(
    X_train,
    y_train_log,
    categorical_feature=categorical_features,
)

print("\nHyperparameter tuning completed.")


# ============================================================
# 11. BEST PARAMETERS
# ============================================================

print("\n" + "=" * 70)
print("BEST HYPERPARAMETERS")
print("=" * 70)

for parameter, value in search.best_params_.items():
    print(f"{parameter:25s}: {value}")

print(
    f"\nBest CV MAE on log-price scale: "
    f"{-search.best_score_:.6f}"
)


# ============================================================
# 12. BEST MODEL
# ============================================================

best_model = search.best_estimator_


# ============================================================
# 13. FINAL TEST PREDICTION
# ============================================================

predicted_log = best_model.predict(X_test)

predicted_price = np.expm1(predicted_log)


# ============================================================
# 14. FINAL TEST METRICS
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
# 15. PRINT FINAL RESULTS
# ============================================================

print("\n" + "=" * 70)
print("TUNED LIGHTGBM FINAL TEST RESULTS")
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
# 16. SAVE MODEL
# ============================================================

model_path = (
    OUTPUT_DIR
    / "lightgbm_tuned_model.joblib"
)

joblib.dump(
    best_model,
    model_path
)


# ============================================================
# 17. SAVE METRICS
# ============================================================

metrics = {
    "model": "LightGBM",
    "tuned": True,
    "cv_folds": 5,
    "n_iter": 20,

    "best_parameters": search.best_params_,

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
# 18. SAVE TEST PREDICTIONS
# ============================================================

predictions = X_test.copy()

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
# 19. FEATURE IMPORTANCE
# ============================================================

feature_importance = pd.DataFrame(
    {
        "feature": best_model.feature_name_,
        "importance": best_model.feature_importances_,
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
# 20. SAVE SEARCH RESULTS
# ============================================================

search_results = pd.DataFrame(
    search.cv_results_
)

search_results_path = (
    OUTPUT_DIR
    / "hyperparameter_search_results.csv"
)

search_results.to_csv(
    search_results_path,
    index=False
)


# ============================================================
# 21. FINAL OUTPUT
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

print(
    f"Search results     : {search_results_path}"
)

print("\n" + "=" * 70)
print("TUNED LIGHTGBM COMPLETE")
print("=" * 70)