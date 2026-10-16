from pathlib import Path

import joblib
import numpy as np
import pandas as pd


# =========================================================
# CONFIGURATION
# =========================================================

DATA_PATH = Path(
    "data/modeling/valuation_modeling_dataset.csv"
)

MODEL_PATH = Path(
    "data/models/lightgbm_tuned/"
    "lightgbm_tuned_model.joblib"
)

TARGET_PROPERTY_ID = "RE-00000001"


# =========================================================
# LOAD DATA
# =========================================================

df = pd.read_csv(DATA_PATH)

print("=" * 80)
print("TARGET PROPERTY ML VALUATION")
print("=" * 80)


# =========================================================
# FIND TARGET
# =========================================================

target_rows = df[
    df["property_id"] == TARGET_PROPERTY_ID
]

if target_rows.empty:
    raise ValueError(
        f"Property {TARGET_PROPERTY_ID} not found."
    )

target = target_rows.iloc[0]


# =========================================================
# MODEL FEATURES
# =========================================================

feature_columns = [
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


categorical_columns = [
    "city",
    "locality",
    "property_type",
]


# =========================================================
# LOAD MODEL
# =========================================================

model = joblib.load(MODEL_PATH)


# =========================================================
# CREATE TARGET DATAFRAME
# =========================================================

X_target = pd.DataFrame(
    [target[feature_columns]],
    columns=feature_columns
)


# =========================================================
# MATCH LIGHTGBM CATEGORICAL TYPES
# =========================================================
#
# The model was trained with categorical columns.
# We recreate the same categorical representation
# before prediction.
#
# The categories are taken from the complete modeling
# dataset, not guessed manually.
# =========================================================

for column in categorical_columns:

    categories = (
        df[column]
        .dropna()
        .astype(str)
        .unique()
    )

    X_target[column] = (
        X_target[column]
        .astype(str)
    )

    X_target[column] = pd.Categorical(
        X_target[column],
        categories=categories
    )


# =========================================================
# PREDICT
# =========================================================

predicted_log_price = model.predict(
    X_target
)[0]


# The model was trained on:
#
# log1p(asking_price_inr)
#
# Convert prediction back to rupees.

predicted_price = np.expm1(
    predicted_log_price
)


# =========================================================
# TARGET INFORMATION
# =========================================================

actual_price = target[
    "asking_price_inr"
]

area = target[
    "valuation_area_sqft"
]


predicted_ppsf = (
    predicted_price / area
)

actual_ppsf = (
    actual_price / area
)


difference_inr = (
    actual_price
    - predicted_price
)

difference_pct = (
    difference_inr
    / predicted_price
) * 100


# =========================================================
# DISPLAY TARGET
# =========================================================

print("\nTARGET PROPERTY")
print("-" * 80)

print(
    f"Property ID       : "
    f"{TARGET_PROPERTY_ID}"
)

print(
    f"City              : "
    f"{target['city']}"
)

print(
    f"Locality          : "
    f"{target['locality']}"
)

print(
    f"Area              : "
    f"{area:,.2f} sqft"
)

print(
    f"Bedrooms          : "
    f"{target['bedrooms']}"
)

print(
    f"Bathrooms         : "
    f"{target['bathrooms']}"
)


# =========================================================
# ML VALUATION
# =========================================================

print("\nML VALUATION")
print("-" * 80)

print(
    f"ML predicted price : "
    f"₹{predicted_price:,.0f}"
)

print(
    f"ML predicted ₹/sqft: "
    f"₹{predicted_ppsf:,.0f}"
)


# =========================================================
# ASKING PRICE COMPARISON
# =========================================================

print("\nASKING PRICE COMPARISON")
print("-" * 80)

print(
    f"Current asking price : "
    f"₹{actual_price:,.0f}"
)

print(
    f"Current asking ₹/sqft: "
    f"₹{actual_ppsf:,.0f}"
)

print(
    f"Difference           : "
    f"₹{difference_inr:,.0f}"
)

print(
    f"Difference vs ML     : "
    f"{difference_pct:+.2f}%"
)


print("\n" + "=" * 80)
print("ML TARGET PREDICTION COMPLETED")
print("=" * 80)