import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "master" / "real_estate_master_v2.csv"
OUTPUT_FILE = BASE_DIR / "data" / "investigation" / "area_mismatches.csv"

SQM_TO_SQFT = 10.7639

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("AREA MISMATCH INVESTIGATION")
print("=" * 75)

df = pd.read_csv(INPUT_FILE, low_memory=False)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df):,}")

# ---------------------------------------------------------
# Select rows where all three fields exist
# ---------------------------------------------------------

cols = [
    "property_id",
    "listing_id",
    "source_city",
    "city",
    "locality",
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft",
    "price_per_sqft",
    "configuration",
    "bedrooms"
]

work = df[cols].dropna(
    subset=[
        "area_sqft_model",
        "area_min_sqft",
        "area_max_sqft"
    ]
).copy()

# ---------------------------------------------------------
# Convert source area from sqm -> sqft
# ---------------------------------------------------------

work["converted_min_sqft"] = (
    work["area_min_sqft"] * SQM_TO_SQFT
)

work["converted_max_sqft"] = (
    work["area_max_sqft"] * SQM_TO_SQFT
)

# ---------------------------------------------------------
# Calculate ratios
# ---------------------------------------------------------

work["model_to_min_ratio"] = (
    work["area_sqft_model"] /
    work["converted_min_sqft"]
)

work["model_to_max_ratio"] = (
    work["area_sqft_model"] /
    work["converted_max_sqft"]
)

work["difference_pct"] = (
    abs(
        work["area_sqft_model"] -
        work["converted_min_sqft"]
    )
    /
    work["area_sqft_model"]
) * 100

# ---------------------------------------------------------
# Identify matching and mismatching records
# ---------------------------------------------------------

work["matches_conversion"] = (
    work["difference_pct"] <= 1
)

mismatches = work[
    ~work["matches_conversion"]
].copy()

print("\n" + "-" * 75)
print("MATCH / MISMATCH SUMMARY")
print("-" * 75)

print(
    f"Total comparable rows : {len(work):,}"
)

print(
    f"Matching rows         : "
    f"{work['matches_conversion'].sum():,}"
)

print(
    f"Mismatching rows      : "
    f"{len(mismatches):,}"
)

# ---------------------------------------------------------
# Ratio distribution
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("RATIO DISTRIBUTION")
print("-" * 75)

print(
    mismatches["model_to_min_ratio"]
    .describe()
    .to_string()
)

# ---------------------------------------------------------
# Common ratio buckets
# ---------------------------------------------------------

def ratio_group(ratio):

    if 0.95 <= ratio <= 1.05:
        return "≈ 1.00"

    if 0.45 <= ratio <= 0.55:
        return "≈ 0.50"

    if 1.95 <= ratio <= 2.05:
        return "≈ 2.00"

    if 9.5 <= ratio <= 12:
        return "≈ 10.76"

    if 0.08 <= ratio <= 0.11:
        return "≈ 0.093"

    if ratio < 0.25:
        return "< 0.25"

    if ratio < 0.75:
        return "0.25–0.75"

    if ratio < 1.25:
        return "0.75–1.25"

    if ratio < 2.5:
        return "1.25–2.50"

    if ratio < 5:
        return "2.50–5.00"

    if ratio < 10:
        return "5.00–10.00"

    if ratio < 20:
        return "10.00–20.00"

    return "> 20"

mismatches["ratio_group"] = (
    mismatches["model_to_min_ratio"]
    .apply(ratio_group)
)

print(
    mismatches["ratio_group"]
    .value_counts()
    .to_string()
)

# ---------------------------------------------------------
# City/source distribution
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("MISMATCHES BY SOURCE CITY")
print("-" * 75)

print(
    mismatches["source_city"]
    .value_counts()
    .head(20)
    .to_string()
)

print("\n" + "-" * 75)
print("MISMATCHES BY ACTUAL CITY")
print("-" * 75)

print(
    mismatches["city"]
    .value_counts()
    .head(20)
    .to_string()
)

# ---------------------------------------------------------
# Show representative examples
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("REPRESENTATIVE MISMATCHES")
print("-" * 75)

display_cols = [
    "property_id",
    "listing_id",
    "source_city",
    "city",
    "locality",
    "area_sqft_model",
    "area_min_sqft",
    "converted_min_sqft",
    "model_to_min_ratio",
    "price_per_sqft",
    "configuration",
    "bedrooms"
]

print(
    mismatches[
        display_cols
    ]
    .sort_values(
        "model_to_min_ratio"
    )
    .head(30)
    .to_string(index=False)
)

# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

mismatches.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("AREA MISMATCH INVESTIGATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")