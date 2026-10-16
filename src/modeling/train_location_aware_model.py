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
# 1. PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "modeling"
    / "valuation_modeling_dataset.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "models"
    / "location_aware"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(INPUT_FILE)

print("=" * 70)
print("LOCATION-AWARE PROPERTY VALUATION MODEL")
print("=" * 70)

print(f"Input rows    : {len(df):,}")
print(f"Input columns : {len(df.columns):,}")


# ============================================================
# 3. SELECT MODEL DATA
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

target = "log_asking_price"

model_df = df[features + [target, "asking_price_inr"]].copy()

model_df = model_df.dropna(subset=[target, "asking_price_inr"])

print(f"Modeling rows : {len(model_df):,}")


# ============================================================
# 4. TRAIN / TEST SPLIT
# ============================================================

train_df, test_df = train_test_split(
    model_df,
    test_size=0.20,
    random_state=42,
)

train_df = train_df.copy()
test_df = test_df.copy()

print(f"Training rows : {len(train_df):,}")
print(f"Testing rows  : {len(test_df):,}")


# ============================================================
# 5. CREATE LEAKAGE-SAFE LOCALITY PPSF
# ============================================================

train_df["actual_price_inr"] = train_df["asking_price_inr"]

train_df["ppsf"] = (
    train_df["actual_price_inr"]
    / train_df["valuation_area_sqft"]
)

# Calculate locality statistics ONLY from training data.
locality_ppsf = (
    train_df
    .dropna(subset=["locality", "ppsf"])
    .groupby("locality")["ppsf"]
    .median()
)

print()
print("Locality PPSF statistics")
print("-" * 70)
print(f"Training localities : {len(locality_ppsf):,}")
print(f"Median PPSF         : ₹{locality_ppsf.median():,.0f}")


# Map training-derived locality PPSF onto both datasets.
train_df["locality_median_ppsf"] = train_df["locality"].map(locality_ppsf)
test_df["locality_median_ppsf"] = test_df["locality"].map(locality_ppsf)


# ============================================================
# 6. CHECK UNSEEN LOCALITIES
# ============================================================

unseen_localities = test_df["locality_median_ppsf"].isna().sum()

print(f"Test records without locality PPSF : {unseen_localities:,}")

# IMPORTANT:
# The missing values are intentional.
# They represent localities that were not present in training.


# ============================================================
# 7. MODEL FEATURES
# ============================================================

numerical_features = [
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "floor",
    "total_floors",
    "locality_median_ppsf",
]

categorical_features = [
    "city",
    "locality",
    "property_type",
]


# ============================================================
# 8. PREPROCESSING
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
            "num",
            numeric_pipeline,
            numerical_features,
        ),
        (
            "cat",
            categorical_pipeline,
            categorical_features,
        ),
    ]
)


# ============================================================
# 9. RANDOM FOREST REGRESSOR
# ============================================================

model = RandomForestRegressor(
    n_estimators=300,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1,
)


# ============================================================
# 10. COMPLETE PIPELINE
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
# 11. TRAIN
# ============================================================

X_train = train_df[
    numerical_features + categorical_features
]

y_train = train_df[target]

X_test = test_df[
    numerical_features + categorical_features
]

y_test = test_df[target]

print()
print("Training model...")
print("-" * 70)

pipeline.fit(X_train, y_train)


# ============================================================
# 12. PREDICTION
# ============================================================

log_predictions = pipeline.predict(X_test)

predicted_prices = np.expm1(log_predictions)
actual_prices = test_df["asking_price_inr"].values


# ============================================================
# 13. EVALUATION
# ============================================================

mae = mean_absolute_error(
    actual_prices,
    predicted_prices,
)

rmse = np.sqrt(
    mean_squared_error(
        actual_prices,
        predicted_prices,
    )
)

r2 = r2_score(
    actual_prices,
    predicted_prices,
)

percentage_errors = (
    np.abs(
        actual_prices - predicted_prices
    )
    / actual_prices
) * 100

mean_absolute_percentage_error = (
    percentage_errors.mean()
)

median_absolute_percentage_error = (
    np.median(percentage_errors)
)

mean_prediction_error = (
    predicted_prices - actual_prices
).mean()


# ============================================================
# 14. PRINT RESULTS
# ============================================================

print()
print("=" * 70)
print("LOCATION-AWARE MODEL RESULTS")
print("=" * 70)

print(f"MAE                         : ₹{mae:,.0f}")
print(f"RMSE                        : ₹{rmse:,.0f}")
print(f"R²                          : {r2:.4f}")
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
    f"₹{mean_prediction_error:,.0f}"
)


# ============================================================
# 15. SAVE PREDICTIONS
# ============================================================

predictions = test_df.copy()

predictions["predicted_price_inr"] = predicted_prices

predictions["prediction_error_inr"] = (
    predicted_prices - actual_prices
)

predictions["absolute_error_inr"] = np.abs(
    predictions["prediction_error_inr"]
)

predictions["absolute_percentage_error"] = (
    predictions["absolute_error_inr"]
    / actual_prices
) * 100

predictions.to_csv(
    OUTPUT_DIR / "test_predictions.csv",
    index=False,
)


# ============================================================
# 16. FEATURE IMPORTANCE
# ============================================================

feature_names = (
    pipeline
    .named_steps["preprocessor"]
    .get_feature_names_out()
)

importances = (
    pipeline
    .named_steps["model"]
    .feature_importances_
)

feature_importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance": importances,
    }
).sort_values(
    "importance",
    ascending=False,
)

feature_importance.to_csv(
    OUTPUT_DIR / "feature_importance.csv",
    index=False,
)


# ============================================================
# 17. SAVE METRICS
# ============================================================

metrics = {
    "model": "RandomForestRegressor",
    "n_estimators": 300,
    "min_samples_leaf": 2,
    "random_state": 42,
    "target": "log_asking_price",
    "prediction_target": "asking_price_inr",
    "train_rows": int(len(train_df)),
    "test_rows": int(len(test_df)),
    "training_localities": int(len(locality_ppsf)),
    "unseen_test_locality_records": int(unseen_localities),
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

with open(
    OUTPUT_DIR / "model_metrics.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        metrics,
        f,
        indent=4,
    )


# ============================================================
# 18. SAVE MODEL
# ============================================================

joblib.dump(
    pipeline,
    OUTPUT_DIR / "location_aware_model.joblib",
)


print()
print("=" * 70)
print("FILES SAVED")
print("=" * 70)

print(
    OUTPUT_DIR / "location_aware_model.joblib"
)

print(
    OUTPUT_DIR / "model_metrics.json"
)

print(
    OUTPUT_DIR / "test_predictions.csv"
)

print(
    OUTPUT_DIR / "feature_importance.csv"
)

print("=" * 70)