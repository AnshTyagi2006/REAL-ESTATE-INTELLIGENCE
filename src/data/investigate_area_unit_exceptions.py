import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "master"
    / "real_estate_master_v2.csv"
)

SQM_TO_SQFT = 10.7639

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("AREA UNIT EXCEPTION INVESTIGATION")
print("=" * 75)

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")

# ---------------------------------------------------------
# Select rows where all three fields exist
# ---------------------------------------------------------

work = df[
    [
        "property_id",
        "listing_id",
        "source_city",
        "source_file",
        "city",
        "locality",
        "area_sqft_model",
        "area_min_sqft",
        "area_max_sqft",
        "price_per_sqft",
        "area_basis",
        "property_type",
        "configuration",
        "bedrooms",
        "bathrooms"
    ]
].dropna(
    subset=[
        "area_sqft_model",
        "area_min_sqft",
        "area_max_sqft"
    ]
).copy()

# ---------------------------------------------------------
# Calculate ratio
# ---------------------------------------------------------

work["ratio"] = (
    work["area_sqft_model"]
    / work["area_min_sqft"]
)

# ---------------------------------------------------------
# Correct classification
# ---------------------------------------------------------

def classify_unit(ratio):

    # area_min is already sqft
    if abs(ratio - 1.0) <= 0.01:
        return "SQFT"

    # area_min is sqm and needs conversion
    if abs(ratio - SQM_TO_SQFT) <= 0.01:
        return "SQM"

    return "UNEXPLAINED"


work["unit_class"] = (
    work["ratio"]
    .apply(classify_unit)
)

# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("FINAL UNIT CLASSIFICATION")
print("-" * 75)

summary = (
    work["unit_class"]
    .value_counts()
)

print(
    summary.to_string()
)

# ---------------------------------------------------------
# Source-level summary
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("UNIT CLASSIFICATION BY SOURCE")
print("-" * 75)

source_summary = (
    work
    .groupby(
        ["source_city", "source_file", "unit_class"]
    )
    .size()
    .reset_index(name="rows")
)

print(
    source_summary.to_string(index=False)
)

# ---------------------------------------------------------
# Show ONLY unexplained records
# ---------------------------------------------------------

exceptions = work[
    work["unit_class"] == "UNEXPLAINED"
].copy()

print("\n" + "-" * 75)
print("TRUE UNIT EXCEPTIONS")
print("-" * 75)

print(
    f"Exception count : {len(exceptions):,}"
)

if len(exceptions) > 0:

    display_cols = [
        "property_id",
        "listing_id",
        "source_city",
        "source_file",
        "city",
        "locality",
        "area_sqft_model",
        "area_min_sqft",
        "area_max_sqft",
        "ratio",
        "price_per_sqft",
        "area_basis",
        "property_type",
        "configuration",
        "bedrooms",
        "bathrooms"
    ]

    print()

    print(
        exceptions[
            display_cols
        ].to_string(index=False)
    )

# ---------------------------------------------------------
# Save exceptions
# ---------------------------------------------------------

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "investigation"
    / "area_unit_exceptions.csv"
)

exceptions.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("AREA UNIT EXCEPTION INVESTIGATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")