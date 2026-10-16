import pandas as pd
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "master"
    / "real_estate_master_v2.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "master"
    / "real_estate_master_v3.csv"
)

REPORT_FILE = (
    BASE_DIR
    / "data"
    / "validation"
    / "master_v3_measurement_report.csv"
)

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("MASTER V3 - CANONICAL MEASUREMENTS")
print("=" * 75)

# ---------------------------------------------------------
# Read Master V2
# ---------------------------------------------------------

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows before : {len(df):,}")
print(f"Columns     : {len(df.columns):,}")

# Keep Master V2 untouched
master = df.copy()

# ---------------------------------------------------------
# Ensure numeric fields
# ---------------------------------------------------------

numeric_fields = [
    "area_sqft",
    "area_sqft_model",
    "superbuiltup_area_sqft",
    "carpet_area_sqft",
    "builtup_area_sqft",
    "price_inr",
    "price_per_sqft"
]

for col in numeric_fields:

    if col in master.columns:

        master[col] = pd.to_numeric(
            master[col],
            errors="coerce"
        )

# ---------------------------------------------------------
# Create canonical valuation area
# ---------------------------------------------------------

master["valuation_area_sqft"] = np.nan

master["valuation_area_source"] = (
    "UNAVAILABLE"
)

master["valuation_area_quality"] = (
    "UNAVAILABLE"
)

# ---------------------------------------------------------
# Priority 1: area_sqft
# ---------------------------------------------------------

mask_area = (
    master["area_sqft"].notna()
    &
    (master["area_sqft"] > 0)
)

master.loc[
    mask_area,
    "valuation_area_sqft"
] = master.loc[
    mask_area,
    "area_sqft"
]

master.loc[
    mask_area,
    "valuation_area_source"
] = "AREA_SQFT"

master.loc[
    mask_area,
    "valuation_area_quality"
] = "DIRECT"

# ---------------------------------------------------------
# Priority 2: area_sqft_model
# ---------------------------------------------------------

mask_model = (
    master["valuation_area_sqft"].isna()
    &
    master["area_sqft_model"].notna()
    &
    (master["area_sqft_model"] > 0)
)

master.loc[
    mask_model,
    "valuation_area_sqft"
] = master.loc[
    mask_model,
    "area_sqft_model"
]

master.loc[
    mask_model,
    "valuation_area_source"
] = "AREA_SQFT_MODEL"

master.loc[
    mask_model,
    "valuation_area_quality"
] = "STANDARDIZED"

# ---------------------------------------------------------
# Priority 3: super built-up area
# ---------------------------------------------------------

mask_super = (
    master["valuation_area_sqft"].isna()
    &
    master["superbuiltup_area_sqft"].notna()
    &
    (master["superbuiltup_area_sqft"] > 0)
)

master.loc[
    mask_super,
    "valuation_area_sqft"
] = master.loc[
    mask_super,
    "superbuiltup_area_sqft"
]

master.loc[
    mask_super,
    "valuation_area_source"
] = "SUPERBUILTUP_AREA"

master.loc[
    mask_super,
    "valuation_area_quality"
] = "FALLBACK"

# ---------------------------------------------------------
# Source PPSF
# ---------------------------------------------------------

master["source_price_per_sqft"] = (
    master["price_per_sqft"]
)

# ---------------------------------------------------------
# Calculate our own PPSF
# ---------------------------------------------------------

master["calculated_price_per_sqft"] = np.nan

mask_ppsf = (
    master["price_inr"].notna()
    &
    (master["price_inr"] > 0)
    &
    master["valuation_area_sqft"].notna()
    &
    (master["valuation_area_sqft"] > 0)
)

master.loc[
    mask_ppsf,
    "calculated_price_per_sqft"
] = (
    master.loc[
        mask_ppsf,
        "price_inr"
    ]
    /
    master.loc[
        mask_ppsf,
        "valuation_area_sqft"
    ]
)

# ---------------------------------------------------------
# PPSF difference
# ---------------------------------------------------------

master["ppsf_difference_pct"] = np.nan

mask_difference = (
    master["source_price_per_sqft"].notna()
    &
    master["source_price_per_sqft"].gt(0)
    &
    master["calculated_price_per_sqft"].notna()
)

master.loc[
    mask_difference,
    "ppsf_difference_pct"
] = (
    abs(
        master.loc[
            mask_difference,
            "calculated_price_per_sqft"
        ]
        -
        master.loc[
            mask_difference,
            "source_price_per_sqft"
        ]
    )
    /
    master.loc[
        mask_difference,
        "source_price_per_sqft"
    ]
) * 100

# ---------------------------------------------------------
# PPSF consistency flag
# ---------------------------------------------------------

master["ppsf_consistency_flag"] = (
    "UNAVAILABLE"
)

consistent = (
    mask_difference
    &
    (master["ppsf_difference_pct"] <= 5)
)

mismatch = (
    mask_difference
    &
    (master["ppsf_difference_pct"] > 5)
)

master.loc[
    consistent,
    "ppsf_consistency_flag"
] = "CONSISTENT"

master.loc[
    mismatch,
    "ppsf_consistency_flag"
] = "SOURCE_MISMATCH"

# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("VALUATION AREA SOURCE")
print("-" * 75)

print(
    master["valuation_area_source"]
    .value_counts(dropna=False)
    .to_string()
)

print("\n" + "-" * 75)
print("VALUATION AREA QUALITY")
print("-" * 75)

print(
    master["valuation_area_quality"]
    .value_counts(dropna=False)
    .to_string()
)

print("\n" + "-" * 75)
print("VALUATION AREA AVAILABILITY")
print("-" * 75)

available_area = (
    master["valuation_area_sqft"]
    .notna()
    .sum()
)

print(
    f"Available valuation area : "
    f"{available_area:,} / "
    f"{len(master):,} "
    f"({available_area / len(master) * 100:.2f}%)"
)

print("\n" + "-" * 75)
print("CALCULATED PPSF")
print("-" * 75)

calculated_count = (
    master["calculated_price_per_sqft"]
    .notna()
    .sum()
)

print(
    f"Calculated PPSF : "
    f"{calculated_count:,}"
)

print("\n" + "-" * 75)
print("PPSF CONSISTENCY")
print("-" * 75)

print(
    master["ppsf_consistency_flag"]
    .value_counts(dropna=False)
    .to_string()
)

# ---------------------------------------------------------
# Report
# ---------------------------------------------------------

report = pd.DataFrame({
    "metric": [
        "rows",
        "valuation_area_available",
        "valuation_area_missing",
        "calculated_ppsf_available",
        "ppsf_consistent",
        "ppsf_source_mismatch",
        "ppsf_unavailable"
    ],
    "value": [
        len(master),
        master["valuation_area_sqft"].notna().sum(),
        master["valuation_area_sqft"].isna().sum(),
        master["calculated_price_per_sqft"].notna().sum(),
        (
            master["ppsf_consistency_flag"]
            == "CONSISTENT"
        ).sum(),
        (
            master["ppsf_consistency_flag"]
            == "SOURCE_MISMATCH"
        ).sum(),
        (
            master["ppsf_consistency_flag"]
            == "UNAVAILABLE"
        ).sum()
    ]
})

# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

master.to_csv(
    OUTPUT_FILE,
    index=False
)

report.to_csv(
    REPORT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Master V3:")
print(OUTPUT_FILE)

print("\nMeasurement report:")
print(REPORT_FILE)

print("\n" + "=" * 75)
print("MASTER V3 MEASUREMENT CREATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")