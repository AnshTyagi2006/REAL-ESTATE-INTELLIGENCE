from pathlib import Path
import json
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data" / "master" / "real_estate_master_v4.csv"

OUTPUT_DIR = ROOT / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DATASET = OUTPUT_DIR / "valuation_modeling_dataset.csv"
PREDICTION_READINESS = OUTPUT_DIR / "prediction_readiness.csv"
REPORT_FILE = OUTPUT_DIR / "valuation_modeling_report.json"


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(INPUT_FILE, low_memory=False)

print("=" * 70)
print("FINAL VALUATION MODELING DATASET")
print("=" * 70)

print(f"Input rows    : {len(df):,}")
print(f"Input columns : {len(df.columns):,}")


# ============================================================
# STEP 1 — BUILD FINAL VALUATION AREA
# ============================================================

# Copy the existing canonical valuation area.
df["final_valuation_area_sqft"] = df["valuation_area_sqft"]

# For properties where the canonical area is missing,
# use area_min_sqft only when area_min_sqft == area_max_sqft.
#
# We already validated that all 4,149 price-only records
# satisfy this condition.

validated_min_max = (
    df["area_min_sqft"].notna()
    & df["area_max_sqft"].notna()
    & (df["area_min_sqft"] > 0)
    & (df["area_min_sqft"] == df["area_max_sqft"])
)

area_augmentation_mask = (
    df["final_valuation_area_sqft"].isna()
    & validated_min_max
)

df.loc[
    area_augmentation_mask,
    "final_valuation_area_sqft"
] = df.loc[
    area_augmentation_mask,
    "area_min_sqft"
]


# ============================================================
# STEP 2 — DETERMINE SUPERVISED TRAINING ELIGIBILITY
# ============================================================

required_training_fields = [
    "asking_price_inr",
    "final_valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
]

training_ready = df[required_training_fields].notna().all(axis=1)

# Numeric validity checks
training_ready &= df["asking_price_inr"] > 0
training_ready &= df["final_valuation_area_sqft"] > 0
training_ready &= df["bedrooms"] > 0
training_ready &= df["bathrooms"] >= 0


# ============================================================
# STEP 3 — CREATE MODELING DATASET
# ============================================================

model_columns = [
    "property_id",
    "listing_id",

    # Target
    "asking_price_inr",

    # Core predictors
    "final_valuation_area_sqft",
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

model_df = df.loc[training_ready, model_columns].copy()

# Rename the final canonical area to the name
# we want to use in the ML pipeline.
model_df.rename(
    columns={
        "final_valuation_area_sqft": "valuation_area_sqft"
    },
    inplace=True,
)

# Log target will be used later because property prices
# are highly right-skewed.
model_df["log_asking_price"] = (
    model_df["asking_price_inr"].apply(lambda x: __import__("math").log1p(x))
)


# ============================================================
# STEP 4 — CREATE PREDICTION READINESS FOR ALL PROPERTIES
# ============================================================

readiness = df[
    [
        "property_id",
        "listing_id",
        "city",
        "locality",
        "bedrooms",
        "bathrooms",
        "latitude",
        "longitude",
        "property_type",
        "floor",
        "total_floors",
        "asking_price_inr",
    ]
].copy()

readiness["valuation_area_sqft"] = df["final_valuation_area_sqft"]

readiness["has_price"] = (
    readiness["asking_price_inr"].notna()
    & (readiness["asking_price_inr"] > 0)
)

readiness["has_area"] = (
    readiness["valuation_area_sqft"].notna()
    & (readiness["valuation_area_sqft"] > 0)
)

readiness["has_location"] = (
    readiness["city"].notna()
    & readiness["locality"].notna()
)

readiness["has_bedrooms"] = (
    readiness["bedrooms"].notna()
    & (readiness["bedrooms"] > 0)
)

readiness["has_bathrooms"] = (
    readiness["bathrooms"].notna()
    & (readiness["bathrooms"] >= 0)
)

readiness["has_coordinates"] = (
    readiness["latitude"].notna()
    & readiness["longitude"].notna()
)

# Minimum information required by our first valuation model.
readiness["core_prediction_features_available"] = (
    readiness["has_area"]
    & readiness["has_location"]
    & readiness["has_bedrooms"]
    & readiness["has_bathrooms"]
)

# Whether this property can be used as a supervised
# training example.
readiness["training_eligible"] = (
    readiness["has_price"]
    & readiness["core_prediction_features_available"]
)


# ============================================================
# STEP 5 — VALIDATION
# ============================================================

duplicate_properties = model_df["property_id"].duplicated().sum()
duplicate_listings = model_df["listing_id"].duplicated().sum()

invalid_prices = (
    (model_df["asking_price_inr"] <= 0)
    | model_df["asking_price_inr"].isna()
).sum()

invalid_areas = (
    (model_df["valuation_area_sqft"] <= 0)
    | model_df["valuation_area_sqft"].isna()
).sum()


# ============================================================
# STEP 6 — REPORT
# ============================================================

report = {
    "input": {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
    },

    "area_augmentation": {
        "records_added_from_validated_min_max": int(
            area_augmentation_mask.sum()
        ),
    },

    "training_dataset": {
        "rows": int(len(model_df)),
        "columns": int(len(model_df.columns)),
        "coverage_percent": round(
            len(model_df) / len(df) * 100, 2
        ),
    },

    "prediction_readiness": {
        "total_properties": int(len(readiness)),
        "has_price": int(readiness["has_price"].sum()),
        "has_area": int(readiness["has_area"].sum()),
        "has_location": int(readiness["has_location"].sum()),
        "has_bedrooms": int(readiness["has_bedrooms"].sum()),
        "has_bathrooms": int(readiness["has_bathrooms"].sum()),
        "has_coordinates": int(readiness["has_coordinates"].sum()),
        "core_prediction_features_available": int(
            readiness["core_prediction_features_available"].sum()
        ),
        "training_eligible": int(
            readiness["training_eligible"].sum()
        ),
    },

    "validation": {
        "duplicate_property_ids": int(duplicate_properties),
        "duplicate_listing_ids": int(duplicate_listings),
        "invalid_prices": int(invalid_prices),
        "invalid_areas": int(invalid_areas),
    },

    "model_target": {
        "target": "asking_price_inr",
        "transformed_target": "log_asking_price",
    },

    "excluded_from_predictors": [
        "asking_price_inr",
        "log_asking_price",
        "source_price_per_sqft",
        "calculated_price_per_sqft",
    ],
}


# ============================================================
# SAVE
# ============================================================

model_df.to_csv(
    MODEL_DATASET,
    index=False
)

readiness.to_csv(
    PREDICTION_READINESS,
    index=False
)

with open(REPORT_FILE, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)


# ============================================================
# TERMINAL OUTPUT
# ============================================================

print("\n" + "=" * 70)
print("RESULT")
print("=" * 70)

print(f"Total properties              : {len(df):,}")
print(
    f"Area added from validated "
    f"min=max records               : {area_augmentation_mask.sum():,}"
)
print(f"Training-ready properties     : {len(model_df):,}")
print(
    f"Training coverage             : "
    f"{len(model_df) / len(df) * 100:.2f}%"
)

print("\nPREDICTION READINESS")
print("-" * 70)

print(
    f"Properties with price         : "
    f"{readiness['has_price'].sum():,}"
)

print(
    f"Properties with area          : "
    f"{readiness['has_area'].sum():,}"
)

print(
    f"Properties with bedrooms      : "
    f"{readiness['has_bedrooms'].sum():,}"
)

print(
    f"Properties with core features : "
    f"{readiness['core_prediction_features_available'].sum():,}"
)

print(
    f"Training eligible             : "
    f"{readiness['training_eligible'].sum():,}"
)

print("\nVALIDATION")
print("-" * 70)

print(f"Duplicate property IDs        : {duplicate_properties}")
print(f"Duplicate listing IDs         : {duplicate_listings}")
print(f"Invalid prices                : {invalid_prices}")
print(f"Invalid valuation areas       : {invalid_areas}")

print("\nFILES CREATED")
print("-" * 70)

print(MODEL_DATASET)
print(PREDICTION_READINESS)
print(REPORT_FILE)

print("\nDone.")