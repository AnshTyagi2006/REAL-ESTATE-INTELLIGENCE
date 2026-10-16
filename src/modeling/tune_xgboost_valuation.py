from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import (
    train_test_split,
    RandomizedSearchCV,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from xgboost import XGBRegressor


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
    / "xgboost_tuned"
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
print("XGBOOST HYPERPARAMETER TUNING")
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
# 4. FEATURE TYPES
# ============================================================

numeric_features = [
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "floor",
    "total_floors",
]

categorical_features = [
    "city",
    "locality",
    "property_type",
]


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
# 7. PREPROCESSING
# ============================================================

numeric_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(strategy="median")
        )
    ]
)


categorical_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(
                strategy="most_frequent"
            )
        ),
        (
            "onehot",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            )
        )
    ]
)


preprocessor = ColumnTransformer(
    transformers=[
        (
            "num",
            numeric_pipeline,
            numeric_features
        ),
        (
            "cat",
            categorical_pipeline,
            categorical_features
        )
    ]
)


# ============================================================
# 8. BASE XGBOOST MODEL
# ============================================================

base_model = XGBRegressor(
    objective="reg:squarederror",
    random_state=42,
    n_jobs=-1,
    eval_metric="rmse",
)


# ============================================================
# 9. COMPLETE PIPELINE
# ============================================================

pipeline = Pipeline(
    steps=[
        (
            "preprocessor",
            preprocessor
        ),
        (
            "model",
            base_model
        )
    ]
)


# ============================================================
# 10. HYPERPARAMETER SEARCH SPACE
# ============================================================

param_distributions = {

    "model__n_estimators": [
        300,
        500,
        700,
        900,
    ],

    "model__learning_rate": [
        0.01,
        0.03,
        0.05,
        0.10,
    ],

    "model__max_depth": [
        3,
        5,
        7,
        9,
    ],

    "model__min_child_weight": [
        1,
        3,
        5,
        10,
    ],

    "model__subsample": [
        0.7,
        0.8,
        0.9,
        1.0,
    ],

    "model__colsample_bytree": [
        0.7,
        0.8,
        0.9,
        1.0,
    ],
}


# ============================================================
# 11. RANDOMIZED SEARCH
# ============================================================

search = RandomizedSearchCV(
    estimator=pipeline,
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
# 12. TRAIN / TUNE
# ============================================================

print("\nStarting hyperparameter tuning...")

search.fit(
    X_train,
    y_train_log
)

print("\nHyperparameter tuning completed.")


# ============================================================
# 13. BEST PARAMETERS
# ============================================================

print("\n" + "=" * 70)
print("BEST HYPERPARAMETERS")
print("=" * 70)

for parameter, value in search.best_params_.items():
    print(
        f"{parameter:30s}: {value}"
    )

print(
    f"\nBest CV MAE on log-price scale: "
    f"{-search.best_score_:.6f}"
)


# ============================================================
# 14. BEST MODEL
# ============================================================

best_model = search.best_estimator_


# ============================================================
# 15. FINAL TEST PREDICTION
# ============================================================

predicted_log = (
    best_model.predict(X_test)
)

predicted_price = np.expm1(
    predicted_log
)


# ============================================================
# 16. FINAL TEST METRICS
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
# 17. PRINT FINAL RESULTS
# ============================================================

print("\n" + "=" * 70)
print("TUNED XGBOOST FINAL TEST RESULTS")
print("=" * 70)

print(
    f"MAE                       : "
    f"₹{mae:,.0f}"
)

print(
    f"RMSE                      : "
    f"₹{rmse:,.0f}"
)

print(
    f"R²                        : "
    f"{r2:.4f}"
)

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
# 18. SAVE MODEL
# ============================================================

model_path = (
    OUTPUT_DIR
    / "xgboost_tuned_model.joblib"
)

joblib.dump(
    best_model,
    model_path
)


# ============================================================
# 19. SAVE METRICS
# ============================================================

metrics = {
    "model": "XGBoost",
    "tuned": True,
    "cv_folds": 5,
    "n_iter": 20,

    "best_parameters": {
        str(key): value
        for key, value
        in search.best_params_.items()
    },

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

with open(
    metrics_path,
    "w"
) as f:

    json.dump(
        metrics,
        f,
        indent=4
    )


# ============================================================
# 20. SAVE TEST PREDICTIONS
# ============================================================

predictions = X_test.copy()

predictions[
    "actual_price_inr"
] = y_test.values

predictions[
    "predicted_price_inr"
] = predicted_price

predictions[
    "absolute_error_inr"
] = np.abs(
    predictions["actual_price_inr"]
    - predictions["predicted_price_inr"]
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
# 21. FEATURE IMPORTANCE
# ============================================================

fitted_preprocessor = (
    best_model
    .named_steps["preprocessor"]
)

fitted_xgb = (
    best_model
    .named_steps["model"]
)

feature_names = (
    fitted_preprocessor
    .get_feature_names_out()
)

feature_importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance":
            fitted_xgb.feature_importances_,
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
# 22. SAVE SEARCH RESULTS
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
# 23. FINAL OUTPUT
# ============================================================

print("\nFiles saved:")

print(
    f"Model             : "
    f"{model_path}"
)

print(
    f"Metrics            : "
    f"{metrics_path}"
)

print(
    f"Predictions        : "
    f"{predictions_path}"
)

print(
    f"Feature importance : "
    f"{feature_importance_path}"
)

print(
    f"Search results     : "
    f"{search_results_path}"
)

print("\n" + "=" * 70)
print("TUNED XGBOOST COMPLETE")
print("=" * 70)
