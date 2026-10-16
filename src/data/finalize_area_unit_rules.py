import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "master" / "real_estate_master_v2.csv"

SQM_TO_SQFT = 10.7639

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("FINAL AREA UNIT RULE INVESTIGATION")
print("=" * 75)

df = pd.read_csv(INPUT_FILE, low_memory=False)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")

# ---------------------------------------------------------
# Select comparable rows
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
        "area_max_sqft"
    ]
].dropna(
    subset=[
        "area_sqft_model",
        "area_min_sqft",
        "area_max_sqft"
    ]
).copy()

# ---------------------------------------------------------
# Compare raw area_min with model area
# ---------------------------------------------------------

work["ratio_raw"] = (
    work["area_sqft_model"] /
    work["area_min_sqft"]
)

# ---------------------------------------------------------
# Classify unit relationship
# ---------------------------------------------------------

def classify_ratio(ratio):

    # Raw value already behaves like sqft
    if abs(ratio - 1.0) <= 0.01:
        return "LIKELY_SQFT"

    # Raw value behaves like sqm
    if abs(ratio - (1 / SQM_TO_SQFT)) <= 0.001:
        return "LIKELY_SQM"

    return "UNEXPLAINED"


work["unit_class"] = (
    work["ratio_raw"]
    .apply(classify_ratio)
)

# ---------------------------------------------------------
# Overall result
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("OVERALL UNIT CLASSIFICATION")
print("-" * 75)

print(
    work["unit_class"]
    .value_counts()
    .to_string()
)

# ---------------------------------------------------------
# Unit classification by source file
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("UNIT CLASSIFICATION BY SOURCE FILE")
print("-" * 75)

source_summary = (
    work
    .groupby(
        ["source_file", "source_city", "unit_class"]
    )
    .size()
    .reset_index(name="rows")
    .sort_values(
        ["source_file", "rows"],
        ascending=[True, False]
    )
)

print(
    source_summary.to_string(index=False)
)

# ---------------------------------------------------------
# Source-level dominant unit
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("SOURCE FILE UNIT SUMMARY")
print("-" * 75)

source_unit = (
    work
    .pivot_table(
        index=["source_file", "source_city"],
        columns="unit_class",
        values="property_id",
        aggfunc="count",
        fill_value=0
    )
    .reset_index()
)

print(
    source_unit.to_string(index=False)
)

# ---------------------------------------------------------
# Unexplained records
# ---------------------------------------------------------

unexplained = work[
    work["unit_class"] == "UNEXPLAINED"
].copy()

print("\n" + "-" * 75)
print("UNEXPLAINED RECORDS")
print("-" * 75)

print(
    f"Count : {len(unexplained):,}"
)

if len(unexplained) > 0:

    print()

    print(
        unexplained[
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
                "ratio_raw"
            ]
        ]
        .to_string(index=False)
    )

# ---------------------------------------------------------
# Check whether source files contain mixed units
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("MIXED-UNIT SOURCE CHECK")
print("-" * 75)

mixed_sources = (
    work
    .groupby("source_file")["unit_class"]
    .nunique()
)

mixed_sources = mixed_sources[
    mixed_sources > 1
]

if len(mixed_sources) == 0:

    print(
        "No source file contains multiple identified unit types."
    )

else:

    print(
        "WARNING: Some source files contain multiple unit types:"
    )

    print(
        mixed_sources.to_string()
    )

# ---------------------------------------------------------
# Save complete classification
# ---------------------------------------------------------

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "investigation"
    / "area_unit_classification.csv"
)

work.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("FINAL AREA UNIT RULE INVESTIGATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")