from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# REAL ESTATE INTELLIGENCE PLATFORM
# CORE MEASUREMENT INVESTIGATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v2.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "investigation"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "core_measurement_summary.csv"
)

CONSISTENCY_FILE = (
    OUTPUT_DIR
    / "core_measurement_consistency.csv"
)


print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("CORE MEASUREMENT INVESTIGATION")
print("=" * 75)


# ============================================================
# 1. LOAD MASTER V2
# ============================================================

print("\nReading Master V2...")

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")


# ============================================================
# 2. DEFINE CORE FIELDS
# ============================================================

price_fields = [
    "price_inr",
    "price_lakh",
    "price_crore",
    "price_min_inr",
    "price_max_inr",
]

area_fields = [
    "area_sqft",
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft",
    "carpet_area_sqft",
    "builtup_area_sqft",
    "superbuiltup_area_sqft",
]

other_fields = [
    "price_per_sqft",
    "bedrooms",
    "bhk",
    "bathrooms",
]


# Keep only fields that actually exist
price_fields = [
    c for c in price_fields
    if c in df.columns
]

area_fields = [
    c for c in area_fields
    if c in df.columns
]

other_fields = [
    c for c in other_fields
    if c in df.columns
]


# ============================================================
# 3. AVAILABILITY SUMMARY
# ============================================================

print("\n" + "-" * 75)
print("PRICE FIELD AVAILABILITY")
print("-" * 75)

summary_rows = []

for field in price_fields:

    non_null = df[field].notna().sum()

    missing = df[field].isna().sum()

    percentage = (
        non_null / len(df) * 100
    )

    print(
        f"{field:<25}"
        f"available={non_null:>7,} "
        f"missing={missing:>7,} "
        f"coverage={percentage:>6.2f}%"
    )

    summary_rows.append({
        "category": "price",
        "field": field,
        "non_null": non_null,
        "missing": missing,
        "coverage_percent": percentage
    })


print("\n" + "-" * 75)
print("AREA FIELD AVAILABILITY")
print("-" * 75)

for field in area_fields:

    non_null = df[field].notna().sum()

    missing = df[field].isna().sum()

    percentage = (
        non_null / len(df) * 100
    )

    print(
        f"{field:<25}"
        f"available={non_null:>7,} "
        f"missing={missing:>7,} "
        f"coverage={percentage:>6.2f}%"
    )

    summary_rows.append({
        "category": "area",
        "field": field,
        "non_null": non_null,
        "missing": missing,
        "coverage_percent": percentage
    })


print("\n" + "-" * 75)
print("OTHER CORE FIELD AVAILABILITY")
print("-" * 75)

for field in other_fields:

    non_null = df[field].notna().sum()

    missing = df[field].isna().sum()

    percentage = (
        non_null / len(df) * 100
    )

    print(
        f"{field:<25}"
        f"available={non_null:>7,} "
        f"missing={missing:>7,} "
        f"coverage={percentage:>6.2f}%"
    )

    summary_rows.append({
        "category": "other",
        "field": field,
        "non_null": non_null,
        "missing": missing,
        "coverage_percent": percentage
    })


summary_df = pd.DataFrame(
    summary_rows
)

summary_df.to_csv(
    SUMMARY_FILE,
    index=False
)


# ============================================================
# 4. PRICE CONSISTENCY
# ============================================================

print("\n" + "-" * 75)
print("PRICE CONSISTENCY")
print("-" * 75)

consistency_rows = []


# ------------------------------------------------------------
# price_inr vs price_lakh
# ------------------------------------------------------------

if {
    "price_inr",
    "price_lakh"
}.issubset(df.columns):

    mask = (
        df["price_inr"].notna()
        &
        df["price_lakh"].notna()
        &
        (df["price_lakh"] > 0)
    )

    expected = (
        df.loc[mask, "price_lakh"]
        * 100000
    )

    actual = (
        df.loc[mask, "price_inr"]
    )

    relative_error = (
        (actual - expected).abs()
        / expected
    )

    exact_or_near = (
        relative_error <= 0.01
    )

    print(
        "\nprice_inr vs price_lakh"
    )

    print(
        f"Comparable rows : {mask.sum():,}"
    )

    print(
        f"Within 1%       : "
        f"{exact_or_near.sum():,} "
        f"({exact_or_near.mean() * 100:.2f}%)"
    )

    consistency_rows.append({
        "comparison": "price_inr_vs_price_lakh",
        "rows_compared": int(mask.sum()),
        "within_1_percent": int(
            exact_or_near.sum()
        ),
        "within_1_percent_pct": (
            exact_or_near.mean() * 100
            if len(exact_or_near) > 0
            else np.nan
        )
    })


# ------------------------------------------------------------
# price_inr vs price_crore
# ------------------------------------------------------------

if {
    "price_inr",
    "price_crore"
}.issubset(df.columns):

    mask = (
        df["price_inr"].notna()
        &
        df["price_crore"].notna()
        &
        (df["price_crore"] > 0)
    )

    expected = (
        df.loc[mask, "price_crore"]
        * 10000000
    )

    actual = (
        df.loc[mask, "price_inr"]
    )

    relative_error = (
        (actual - expected).abs()
        / expected
    )

    exact_or_near = (
        relative_error <= 0.01
    )

    print(
        "\nprice_inr vs price_crore"
    )

    print(
        f"Comparable rows : {mask.sum():,}"
    )

    print(
        f"Within 1%       : "
        f"{exact_or_near.sum():,} "
        f"({exact_or_near.mean() * 100:.2f}%)"
    )

    consistency_rows.append({
        "comparison": "price_inr_vs_price_crore",
        "rows_compared": int(mask.sum()),
        "within_1_percent": int(
            exact_or_near.sum()
        ),
        "within_1_percent_pct": (
            exact_or_near.mean() * 100
            if len(exact_or_near) > 0
            else np.nan
        )
    })


# ============================================================
# 5. PRICE RANGE CONSISTENCY
# ============================================================

if {
    "price_min_inr",
    "price_max_inr"
}.issubset(df.columns):

    mask = (
        df["price_min_inr"].notna()
        &
        df["price_max_inr"].notna()
    )

    invalid_range = (
        df.loc[mask, "price_min_inr"]
        >
        df.loc[mask, "price_max_inr"]
    )

    print(
        "\nprice_min_inr <= price_max_inr"
    )

    print(
        f"Comparable rows : {mask.sum():,}"
    )

    print(
        f"Invalid ranges  : "
        f"{invalid_range.sum():,}"
    )

    consistency_rows.append({
        "comparison": "price_min_vs_price_max",
        "rows_compared": int(mask.sum()),
        "within_1_percent": np.nan,
        "within_1_percent_pct": np.nan,
        "invalid_ranges": int(
            invalid_range.sum()
        )
    })


# ============================================================
# 6. AREA RANGE CONSISTENCY
# ============================================================

if {
    "area_min_sqft",
    "area_max_sqft"
}.issubset(df.columns):

    mask = (
        df["area_min_sqft"].notna()
        &
        df["area_max_sqft"].notna()
    )

    invalid_range = (
        df.loc[mask, "area_min_sqft"]
        >
        df.loc[mask, "area_max_sqft"]
    )

    print(
        "\narea_min_sqft <= area_max_sqft"
    )

    print(
        f"Comparable rows : {mask.sum():,}"
    )

    print(
        f"Invalid ranges  : "
        f"{invalid_range.sum():,}"
    )

    consistency_rows.append({
        "comparison": "area_min_vs_area_max",
        "rows_compared": int(mask.sum()),
        "within_1_percent": np.nan,
        "within_1_percent_pct": np.nan,
        "invalid_ranges": int(
            invalid_range.sum()
        )
    })


# ============================================================
# 7. PRICE PER SQFT CONSISTENCY
# ============================================================

print("\n" + "-" * 75)
print("PRICE PER SQFT CONSISTENCY")
print("-" * 75)


if {
    "price_inr",
    "area_sqft",
    "price_per_sqft"
}.issubset(df.columns):

    mask = (
        df["price_inr"].notna()
        &
        df["area_sqft"].notna()
        &
        df["price_per_sqft"].notna()
        &
        (df["area_sqft"] > 0)
        &
        (df["price_inr"] > 0)
    )

    calculated_ppsf = (
        df.loc[mask, "price_inr"]
        /
        df.loc[mask, "area_sqft"]
    )

    reported_ppsf = (
        df.loc[mask, "price_per_sqft"]
    )

    relative_error = (
        (reported_ppsf - calculated_ppsf).abs()
        /
        calculated_ppsf
    )

    within_1 = (
        relative_error <= 0.01
    )

    within_5 = (
        relative_error <= 0.05
    )

    within_10 = (
        relative_error <= 0.10
    )

    print(
        f"Comparable rows : {mask.sum():,}"
    )

    print(
        f"Within 1%       : "
        f"{within_1.sum():,} "
        f"({within_1.mean() * 100:.2f}%)"
    )

    print(
        f"Within 5%       : "
        f"{within_5.sum():,} "
        f"({within_5.mean() * 100:.2f}%)"
    )

    print(
        f"Within 10%      : "
        f"{within_10.sum():,} "
        f"({within_10.mean() * 100:.2f}%)"
    )

    consistency_rows.append({
        "comparison": "price_per_sqft_calculation",
        "rows_compared": int(mask.sum()),
        "within_1_percent": int(
            within_1.sum()
        ),
        "within_1_percent_pct": (
            within_1.mean() * 100
        ),
        "within_5_percent": int(
            within_5.sum()
        ),
        "within_5_percent_pct": (
            within_5.mean() * 100
        ),
        "within_10_percent": int(
            within_10.sum()
        ),
        "within_10_percent_pct": (
            within_10.mean() * 100
        )
    })

else:

    print(
        "Required fields are not available."
    )


# ============================================================
# 8. AREA MODEL CONSISTENCY
# ============================================================

print("\n" + "-" * 75)
print("AREA MODEL CONSISTENCY")
print("-" * 75)


if {
    "area_sqft",
    "area_sqft_model"
}.issubset(df.columns):

    mask = (
        df["area_sqft"].notna()
        &
        df["area_sqft_model"].notna()
        &
        (df["area_sqft"] > 0)
    )

    actual = (
        df.loc[mask, "area_sqft"]
    )

    model = (
        df.loc[mask, "area_sqft_model"]
    )

    relative_error = (
        (actual - model).abs()
        /
        actual
    )

    within_1 = (
        relative_error <= 0.01
    )

    within_5 = (
        relative_error <= 0.05
    )

    within_10 = (
        relative_error <= 0.10
    )

    print(
        f"Comparable rows : {mask.sum():,}"
    )

    print(
        f"Within 1%       : "
        f"{within_1.sum():,} "
        f"({within_1.mean() * 100:.2f}%)"
    )

    print(
        f"Within 5%       : "
        f"{within_5.sum():,} "
        f"({within_5.mean() * 100:.2f}%)"
    )

    print(
        f"Within 10%      : "
        f"{within_10.sum():,} "
        f"({within_10.mean() * 100:.2f}%)"
    )

    consistency_rows.append({
        "comparison": "area_sqft_vs_area_sqft_model",
        "rows_compared": int(mask.sum()),
        "within_1_percent": int(
            within_1.sum()
        ),
        "within_1_percent_pct": (
            within_1.mean() * 100
        ),
        "within_5_percent": int(
            within_5.sum()
        ),
        "within_5_percent_pct": (
            within_5.mean() * 100
        ),
        "within_10_percent": int(
            within_10.sum()
        ),
        "within_10_percent_pct": (
            within_10.mean() * 100
        )
    })

else:

    print(
        "Required fields are not available."
    )


# ============================================================
# 9. PRICE + AREA USABILITY
# ============================================================

print("\n" + "-" * 75)
print("PRICE + AREA USABILITY")
print("-" * 75)


price_available = (
    df[price_fields]
    .notna()
    .any(axis=1)
)

area_available = (
    df[area_fields]
    .notna()
    .any(axis=1)
)

both_available = (
    price_available
    &
    area_available
)

print(
    f"Any usable price field : "
    f"{price_available.sum():,} "
    f"({price_available.mean() * 100:.2f}%)"
)

print(
    f"Any usable area field  : "
    f"{area_available.sum():,} "
    f"({area_available.mean() * 100:.2f}%)"
)

print(
    f"Both price + area      : "
    f"{both_available.sum():,} "
    f"({both_available.mean() * 100:.2f}%)"
)


# ============================================================
# 10. SAVE CONSISTENCY REPORT
# ============================================================

consistency_df = pd.DataFrame(
    consistency_rows
)

consistency_df.to_csv(
    CONSISTENCY_FILE,
    index=False
)


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "-" * 75)
print("OUTPUT FILES")
print("-" * 75)

print(
    f"Summary:\n{SUMMARY_FILE}"
)

print(
    f"\nConsistency:\n{CONSISTENCY_FILE}"
)

print("\n" + "=" * 75)
print("CORE MEASUREMENT INVESTIGATION COMPLETE")
print("=" * 75)

print("\nIMPORTANT:")
print("Master V2 was NOT modified.")
print("No values were filled or replaced.")
print("This step only investigated availability and consistency.")