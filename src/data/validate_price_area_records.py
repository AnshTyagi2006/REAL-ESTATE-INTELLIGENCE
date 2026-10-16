from pathlib import Path
import pandas as pd


# ============================================================
# VALIDATE PRICE + AREA RECORDS
#
# Purpose:
# Check whether area_min_sqft and area_max_sqft represent
# a single property area for the 4,149 price-only records.
#
# We DO NOT modify the dataset in this script.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v4.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "investigation"
OUTPUT_FILE = OUTPUT_DIR / "price_area_validation.csv"


# ------------------------------------------------------------
# 1. Load data
# ------------------------------------------------------------

df = pd.read_csv(INPUT_FILE, low_memory=False)

print("=" * 70)
print("PRICE + AREA RECORD VALIDATION")
print("=" * 70)

print(f"Total properties: {len(df):,}")


# ------------------------------------------------------------
# 2. Select the 4,149 price-only records
# ------------------------------------------------------------

has_price = (
    df["asking_price_inr"].notna()
    & (df["asking_price_inr"] > 0)
)

has_valuation_area = (
    df["valuation_area_sqft"].notna()
    & (df["valuation_area_sqft"] > 0)
)

price_only = has_price & ~has_valuation_area

subset = df.loc[price_only].copy()

print(f"Price-only records selected: {len(subset):,}")


# ------------------------------------------------------------
# 3. Convert area fields to numeric
# ------------------------------------------------------------

subset["area_min_sqft_num"] = pd.to_numeric(
    subset["area_min_sqft"],
    errors="coerce"
)

subset["area_max_sqft_num"] = pd.to_numeric(
    subset["area_max_sqft"],
    errors="coerce"
)


# ------------------------------------------------------------
# 4. Check availability
# ------------------------------------------------------------

has_min = (
    subset["area_min_sqft_num"].notna()
    & (subset["area_min_sqft_num"] > 0)
)

has_max = (
    subset["area_max_sqft_num"].notna()
    & (subset["area_max_sqft_num"] > 0)
)

print("\nAREA AVAILABILITY")
print("-" * 70)

print(f"Valid area_min_sqft: {has_min.sum():,}")
print(f"Valid area_max_sqft: {has_max.sum():,}")


# ------------------------------------------------------------
# 5. Check whether min == max
# ------------------------------------------------------------

both_available = has_min & has_max

same_area = (
    both_available
    & (
        (subset["area_min_sqft_num"] - subset["area_max_sqft_num"]).abs()
        < 0.01
    )
)

different_area = both_available & ~same_area

print("\nMIN / MAX RELATIONSHIP")
print("-" * 70)

print(f"Both available : {both_available.sum():,}")
print(f"Min = Max      : {same_area.sum():,}")
print(f"Min != Max     : {different_area.sum():,}")


# ------------------------------------------------------------
# 6. Inspect actual ranges
# ------------------------------------------------------------

if different_area.sum() > 0:

    subset.loc[
        different_area,
        "area_range_width_sqft"
    ] = (
        subset.loc[different_area, "area_max_sqft_num"]
        - subset.loc[different_area, "area_min_sqft_num"]
    )

    print("\nEXAMPLES WHERE MIN != MAX")
    print("-" * 70)

    columns = [
        "property_id",
        "listing_id",
        "city",
        "locality",
        "configuration",
        "bedrooms",
        "asking_price_inr",
        "area_min_sqft_num",
        "area_max_sqft_num",
    ]

    available_columns = [
        col for col in columns
        if col in subset.columns
    ]

    print(
        subset.loc[
            different_area,
            available_columns
        ]
        .head(20)
        .to_string(index=False)
    )


# ------------------------------------------------------------
# 7. Check city distribution
# ------------------------------------------------------------

city_summary = (
    subset.assign(
        single_area=same_area.loc[subset.index],
        genuine_range=different_area.loc[subset.index]
    )
    .groupby("city", dropna=False)
    .agg(
        records=("property_id", "size"),
        single_area=("single_area", "sum"),
        non_equal_range=("genuine_range", "sum"),
    )
    .reset_index()
)

print("\nCITY VALIDATION")
print("-" * 70)

print(city_summary.to_string(index=False))


# ------------------------------------------------------------
# 8. Check whether other direct area fields exist
# ------------------------------------------------------------

direct_area_columns = [
    "area_sqft",
    "carpet_area_sqft",
    "builtup_area_sqft",
    "superbuiltup_area_sqft",
]

print("\nOTHER AREA FIELDS")
print("-" * 70)

for col in direct_area_columns:

    if col not in subset.columns:
        continue

    available = (
        pd.to_numeric(
            subset[col],
            errors="coerce"
        )
        .gt(0)
        .sum()
    )

    print(f"{col:<30}: {available:,}")


# ------------------------------------------------------------
# 9. Save report
# ------------------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

city_summary.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nREPORT SAVED")
print("-" * 70)
print(OUTPUT_FILE)


# ------------------------------------------------------------
# 10. Final decision guidance
# ------------------------------------------------------------

print("\nDECISION")
print("-" * 70)

if (
    both_available.sum() == same_area.sum()
    and same_area.sum() == len(subset)
):

    print(
        "ALL 4,149 records have area_min_sqft = area_max_sqft."
    )

    print(
        "This supports treating the value as a single property-area "
        "measurement rather than a genuine area range."
    )

    print(
        "NEXT: We can standardize this value into valuation_area_sqft."
    )

else:

    print(
        "NOT ALL records have equal min/max area."
    )

    print(
        "We must inspect the non-equal records before using them "
        "for ML training."
    )

print("=" * 70)