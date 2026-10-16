from pathlib import Path
import json
import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "data" / "master" / "real_estate_master_v4.csv"

OUTPUT_DIR = ROOT / "data" / "audit"
REPORT = OUTPUT_DIR / "final_valuation_audit.json"


# ============================================================
# LOAD
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("FINAL VALUATION DATA AUDIT")
print("=" * 75)

df = pd.read_csv(INPUT, low_memory=False)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")


# ============================================================
# VALUATION CANDIDATES
# ============================================================

candidate_mask = (
    df["asking_price_inr"].notna()
    & (df["asking_price_inr"] > 0)
    & df["valuation_area_sqft"].notna()
    & (df["valuation_area_sqft"] > 0)
)

candidates = df.loc[candidate_mask].copy()

print("\n" + "-" * 75)
print("VALUATION CANDIDATES")
print("-" * 75)

print(f"Candidates : {len(candidates):,}")


# ============================================================
# CALCULATED PPSF
# ============================================================

candidates["calculated_ppsf"] = (
    candidates["asking_price_inr"]
    / candidates["valuation_area_sqft"]
)


# ============================================================
# BASIC VALIDITY
# ============================================================

print("\n" + "-" * 75)
print("BASIC VALIDITY")
print("-" * 75)

checks = {}

checks["invalid_price"] = int(
    (
        candidates["asking_price_inr"] <= 0
    ).sum()
)

checks["invalid_area"] = int(
    (
        candidates["valuation_area_sqft"] <= 0
    ).sum()
)

checks["invalid_ppsf"] = int(
    (
        candidates["calculated_ppsf"] <= 0
    ).sum()
)

checks["missing_city"] = int(
    candidates["city"].isna().sum()
)

checks["missing_locality"] = int(
    candidates["locality"].isna().sum()
)

checks["missing_bedrooms"] = int(
    candidates["bedrooms"].isna().sum()
)

checks["missing_bathrooms"] = int(
    candidates["bathrooms"].isna().sum()
)

for name, value in checks.items():
    print(f"{name:<25}: {value:,}")


# ============================================================
# DISTRIBUTION SUMMARY
# ============================================================

print("\n" + "-" * 75)
print("VALUATION VARIABLE DISTRIBUTIONS")
print("-" * 75)

distribution_fields = [
    "asking_price_inr",
    "valuation_area_sqft",
    "calculated_ppsf",
    "bedrooms",
    "bathrooms",
    "floor",
    "total_floors",
]


distribution_summary = {}

for col in distribution_fields:

    if col not in candidates.columns:
        continue

    s = pd.to_numeric(
        candidates[col],
        errors="coerce"
    ).dropna()

    if len(s) == 0:
        continue

    q1 = s.quantile(0.25)
    median = s.quantile(0.50)
    q3 = s.quantile(0.75)
    p99 = s.quantile(0.99)

    distribution_summary[col] = {
        "count": int(len(s)),
        "min": float(s.min()),
        "q1": float(q1),
        "median": float(median),
        "q3": float(q3),
        "p99": float(p99),
        "max": float(s.max()),
        "mean": float(s.mean()),
    }

    print(f"\n{col}")
    print(f"  Min    : {s.min():,.2f}")
    print(f"  Q1     : {q1:,.2f}")
    print(f"  Median : {median:,.2f}")
    print(f"  Q3     : {q3:,.2f}")
    print(f"  P99    : {p99:,.2f}")
    print(f"  Max    : {s.max():,.2f}")


# ============================================================
# OUTLIER COUNTS USING IQR
# ============================================================

print("\n" + "-" * 75)
print("IQR OUTLIER SCREEN")
print("-" * 75)

outlier_summary = {}

for col in [
    "asking_price_inr",
    "valuation_area_sqft",
    "calculated_ppsf",
]:

    s = pd.to_numeric(
        candidates[col],
        errors="coerce"
    ).dropna()

    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)

    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    mask = (
        (candidates[col] < lower)
        | (candidates[col] > upper)
    )

    count = int(mask.sum())

    outlier_summary[col] = {
        "lower_bound": float(lower),
        "upper_bound": float(upper),
        "count": count,
        "percentage": round(
            count / len(candidates) * 100,
            2
        ),
    }

    print(
        f"{col:<25}: "
        f"{count:,} "
        f"({count / len(candidates) * 100:.2f}%)"
    )


# ============================================================
# CITY DISTRIBUTION
# ============================================================

print("\n" + "-" * 75)
print("CANDIDATES BY CITY")
print("-" * 75)

city_counts = (
    candidates["city"]
    .value_counts()
)

print(city_counts.to_string())


# ============================================================
# PROPERTY TYPE
# ============================================================

print("\n" + "-" * 75)
print("PROPERTY TYPE")
print("-" * 75)

property_type_counts = (
    candidates["property_type"]
    .value_counts(dropna=False)
)

print(
    property_type_counts.to_string()
)


# ============================================================
# CORE MISSINGNESS
# ============================================================

print("\n" + "-" * 75)
print("CORE FEATURE MISSINGNESS")
print("-" * 75)

core_features = [
    "asking_price_inr",
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
    "furnishing",
]


missingness = {}

for col in core_features:

    if col not in candidates.columns:
        continue

    missing = int(
        candidates[col].isna().sum()
    )

    missingness[col] = {
        "missing": missing,
        "percentage": round(
            missing / len(candidates) * 100,
            2
        ),
    }

    print(
        f"{col:<25}: "
        f"{missing:,} "
        f"({missing / len(candidates) * 100:.2f}%)"
    )


# ============================================================
# EXTREME RECORDS
# ============================================================

print("\n" + "-" * 75)
print("EXTREME RECORDS")
print("-" * 75)

extreme_columns = [
    "property_id",
    "listing_id",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    "valuation_area_sqft",
    "asking_price_inr",
    "calculated_ppsf",
]

extreme_columns = [
    col for col in extreme_columns
    if col in candidates.columns
]


top_price = (
    candidates
    .sort_values(
        "asking_price_inr",
        ascending=False
    )
    [extreme_columns]
    .head(15)
)

top_area = (
    candidates
    .sort_values(
        "valuation_area_sqft",
        ascending=False
    )
    [extreme_columns]
    .head(15)
)

top_ppsf = (
    candidates
    .sort_values(
        "calculated_ppsf",
        ascending=False
    )
    [extreme_columns]
    .head(15)
)


print("\nTop prices:")
print(top_price.to_string(index=False))

print("\nTop areas:")
print(top_area.to_string(index=False))

print("\nTop calculated PPSF:")
print(top_ppsf.to_string(index=False))


# ============================================================
# DUPLICATE PROPERTY CHECK
# ============================================================

print("\n" + "-" * 75)
print("DUPLICATE CHECK")
print("-" * 75)

duplicate_listing_ids = int(
    candidates["listing_id"]
    .duplicated()
    .sum()
)

duplicate_property_ids = int(
    candidates["property_id"]
    .duplicated()
    .sum()
)

print(
    f"Duplicate listing IDs : "
    f"{duplicate_listing_ids:,}"
)

print(
    f"Duplicate property IDs : "
    f"{duplicate_property_ids:,}"
)


# ============================================================
# MODEL READINESS
# ============================================================

model_features = [
    "asking_price_inr",
    "valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "property_type",
]

model_ready_mask = (
    candidates[model_features]
    .notna()
    .all(axis=1)
)

model_ready_count = int(
    model_ready_mask.sum()
)

print("\n" + "-" * 75)
print("MODEL READINESS")
print("-" * 75)

print(
    f"Core model-ready records : "
    f"{model_ready_count:,}"
)

print(
    f"Model-ready percentage   : "
    f"{model_ready_count / len(df) * 100:.2f}% "
    f"of full dataset"
)


# ============================================================
# SAVE REPORT
# ============================================================

report = {
    "dataset_rows": int(len(df)),
    "dataset_columns": int(len(df.columns)),
    "valuation_candidates": int(len(candidates)),

    "basic_validity": checks,

    "distributions": distribution_summary,

    "iqr_outliers": outlier_summary,

    "city_distribution":
        city_counts.to_dict(),

    "property_type_distribution":
        property_type_counts.astype(str).to_dict(),

    "missingness": missingness,

    "duplicates": {
        "duplicate_listing_ids":
            duplicate_listing_ids,
        "duplicate_property_ids":
            duplicate_property_ids,
    },

    "model_ready_records":
        model_ready_count,

    "model_features":
        model_features,
}


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    REPORT,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        report,
        f,
        indent=4,
        default=str
    )


# ============================================================
# FINAL
# ============================================================

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print(f"Audit report:\n{REPORT}")

print("\n" + "=" * 75)
print("FINAL VALUATION AUDIT COMPLETE")
print("=" * 75)

print("\nMaster V4 was NOT modified.")