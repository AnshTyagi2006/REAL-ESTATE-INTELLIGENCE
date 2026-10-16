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
from sklearn.model_selection import GroupShuffleSplit


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

MODEL_FILE = (
    ROOT
    / "data"
    / "models"
    / "baseline"
    / "baseline_model.joblib"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "models"
    / "baseline"
    / "diagnostics"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# LOAD DATA + MODEL
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False,
)

model = joblib.load(
    MODEL_FILE
)

print("=" * 70)
print("BASELINE MODEL DIAGNOSTICS")
print("=" * 70)

print(f"Dataset rows : {len(df):,}")


# ============================================================
# SAME TEST SPLIT USED DURING BASELINE TRAINING
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
y = df[LOG_TARGET].copy()

# Recreate the exact same 80/20 split used in
# train_baseline_valuation.py.
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
)

# Identify the original test rows using their indices.
test_indices = X_test.index

test_df = df.loc[test_indices].copy()

pred_log = model.predict(X_test)

pred_price = np.expm1(
    pred_log
)

actual_price = np.expm1(
    y_test
)


# ============================================================
# HELPER FUNCTION
# ============================================================

def calculate_metrics(actual, predicted):
    """Calculate the main regression metrics."""

    mae = mean_absolute_error(
        actual,
        predicted,
    )

    rmse = np.sqrt(
        mean_squared_error(
            actual,
            predicted,
        )
    )

    r2 = r2_score(
        actual,
        predicted,
    )

    percentage_error = (
        np.abs(actual - predicted)
        / actual
        * 100
    )

    return {
        "records": int(len(actual)),
        "mae_inr": float(mae),
        "rmse_inr": float(rmse),
        "r2": float(r2),
        "mean_absolute_percentage_error": float(
            np.mean(percentage_error)
        ),
        "median_absolute_percentage_error": float(
            np.median(percentage_error)
        ),
    }


# ============================================================
# ADD PREDICTIONS TO TEST DATA
# ============================================================

test_df["predicted_price_inr"] = pred_price

test_df["absolute_error_inr"] = np.abs(
    actual_price - pred_price
)

test_df["percentage_error"] = (
    test_df["absolute_error_inr"]
    / actual_price
    * 100
)

test_df["signed_error_inr"] = (
    pred_price - actual_price
)


# ============================================================
# 1. CITY-LEVEL PERFORMANCE
# ============================================================

city_results = []

for city, group in test_df.groupby(
    "city",
    dropna=False,
):

    actual = group[TARGET].values
    predicted = group[
        "predicted_price_inr"
    ].values

    metrics = calculate_metrics(
        actual,
        predicted,
    )

    metrics["city"] = city

    city_results.append(
        metrics
    )

city_metrics = pd.DataFrame(
    city_results
)

city_metrics = city_metrics[
    [
        "city",
        "records",
        "mae_inr",
        "rmse_inr",
        "r2",
        "mean_absolute_percentage_error",
        "median_absolute_percentage_error",
    ]
].sort_values(
    "records",
    ascending=False,
)

city_metrics.to_csv(
    OUTPUT_DIR / "city_metrics.csv",
    index=False,
)


# ============================================================
# 2. PRICE-BAND PERFORMANCE
# ============================================================

# Price is stored in INR.
# These bands are only for diagnostic analysis.

price_bins = [
    0,
    10_000_000,       # ₹1 Cr
    20_000_000,       # ₹2 Cr
    50_000_000,       # ₹5 Cr
    np.inf,
]

price_labels = [
    "< ₹1 Cr",
    "₹1–2 Cr",
    "₹2–5 Cr",
    "> ₹5 Cr",
]

test_df["price_band"] = pd.cut(
    test_df[TARGET],
    bins=price_bins,
    labels=price_labels,
    right=False,
)

price_band_results = []

for band, group in test_df.groupby(
    "price_band",
    observed=False,
):

    if len(group) == 0:
        continue

    actual = group[TARGET].values

    predicted = group[
        "predicted_price_inr"
    ].values

    metrics = calculate_metrics(
        actual,
        predicted,
    )

    metrics["price_band"] = str(
        band
    )

    price_band_results.append(
        metrics
    )

price_band_metrics = pd.DataFrame(
    price_band_results
)

price_band_metrics = price_band_metrics[
    [
        "price_band",
        "records",
        "mae_inr",
        "rmse_inr",
        "r2",
        "mean_absolute_percentage_error",
        "median_absolute_percentage_error",
    ]
]

price_band_metrics.to_csv(
    OUTPUT_DIR / "price_band_metrics.csv",
    index=False,
)


# ============================================================
# 3. WORST PREDICTIONS
# ============================================================

worst_predictions = test_df[
    [
        "property_id",
        "listing_id",
        "city",
        "locality",
        "valuation_area_sqft",
        "bedrooms",
        "bathrooms",
        TARGET,
        "predicted_price_inr",
        "absolute_error_inr",
        "percentage_error",
    ]
].sort_values(
    "percentage_error",
    ascending=False,
)

worst_predictions.head(50).to_csv(
    OUTPUT_DIR / "worst_predictions.csv",
    index=False,
)


# ============================================================
# 4. LOCALITY-GROUPED VALIDATION
# ============================================================

print("\nRunning locality-grouped validation...")

groups = df["locality"].fillna(
    "__MISSING_LOCALITY__"
)

group_splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.20,
    random_state=42,
)

train_indices, grouped_test_indices = next(
    group_splitter.split(
        X,
        y,
        groups=groups,
    )
)

X_group_train = X.iloc[
    train_indices
]

X_group_test = X.iloc[
    grouped_test_indices
]

y_group_train = y.iloc[
    train_indices
]

y_group_test = y.iloc[
    grouped_test_indices
]


# Train a fresh copy of the same baseline model.
#
# This is necessary because the existing baseline was trained
# using the random split. We need a model trained WITHOUT
# seeing the test localities.

from sklearn.base import clone

grouped_model = clone(
    model
)

grouped_model.fit(
    X_group_train,
    y_group_train,
)

grouped_pred_log = grouped_model.predict(
    X_group_test
)

grouped_pred_price = np.expm1(
    grouped_pred_log
)

grouped_actual_price = np.expm1(
    y_group_test
)

grouped_metrics = calculate_metrics(
    grouped_actual_price,
    grouped_pred_price,
)

# Count how many unique localities were used.
train_localities = set(
    groups.iloc[train_indices]
)

test_localities = set(
    groups.iloc[grouped_test_indices]
)

overlap = (
    train_localities
    & test_localities
)

grouped_report = {
    "method": "GroupShuffleSplit by locality",
    "total_records": int(len(df)),
    "training_records": int(
        len(train_indices)
    ),
    "test_records": int(
        len(grouped_test_indices)
    ),
    "training_localities": int(
        len(train_localities)
    ),
    "test_localities": int(
        len(test_localities)
    ),
    "locality_overlap": int(
        len(overlap)
    ),
    "metrics": grouped_metrics,
}


with open(
    OUTPUT_DIR
    / "grouped_validation_metrics.json",
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        grouped_report,
        file,
        indent=2,
    )


# ============================================================
# TERMINAL OUTPUT
# ============================================================

print("\n" + "=" * 70)
print("CITY PERFORMANCE")
print("=" * 70)

print(
    city_metrics.to_string(
        index=False
    )
)


print("\n" + "=" * 70)
print("PRICE-BAND PERFORMANCE")
print("=" * 70)

print(
    price_band_metrics.to_string(
        index=False
    )
)


print("\n" + "=" * 70)
print("WORST PREDICTIONS")
print("=" * 70)

print(
    worst_predictions.head(10)[
        [
            "city",
            "locality",
            TARGET,
            "predicted_price_inr",
            "percentage_error",
        ]
    ].to_string(
        index=False
    )
)


print("\n" + "=" * 70)
print("LOCALITY-GROUPED VALIDATION")
print("=" * 70)

print(
    f"Training records       : "
    f"{len(train_indices):,}"
)

print(
    f"Testing records        : "
    f"{len(grouped_test_indices):,}"
)

print(
    f"Training localities    : "
    f"{len(train_localities):,}"
)

print(
    f"Testing localities     : "
    f"{len(test_localities):,}"
)

print(
    f"Locality overlap       : "
    f"{len(overlap)}"
)

print("\nGrouped-validation metrics:")

for key, value in grouped_metrics.items():

    if key == "mae_inr":
        print(
            f"MAE                    : ₹{value:,.0f}"
        )

    elif key == "rmse_inr":
        print(
            f"RMSE                   : ₹{value:,.0f}"
        )

    elif key == "r2":
        print(
            f"R²                     : {value:.4f}"
        )

    elif key == "mean_absolute_percentage_error":
        print(
            f"Mean Absolute % Error  : {value:.2f}%"
        )

    elif key == "median_absolute_percentage_error":
        print(
            f"Median Absolute % Error: {value:.2f}%"
        )


print("\n" + "=" * 70)
print("DIAGNOSTIC FILES CREATED")
print("=" * 70)

print(
    OUTPUT_DIR / "city_metrics.csv"
)

print(
    OUTPUT_DIR / "price_band_metrics.csv"
)

print(
    OUTPUT_DIR / "worst_predictions.csv"
)

print(
    OUTPUT_DIR / "grouped_validation_metrics.json"
)

print("\nBaseline diagnostics complete.")