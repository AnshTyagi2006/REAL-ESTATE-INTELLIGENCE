import pandas as pd
from pathlib import Path

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
    / "investigation"
    / "ppsf_mismatch_analysis.csv"
)

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("PRICE/SQFT MISMATCH INVESTIGATION")
print("=" * 75)

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")

# ---------------------------------------------------------
# Use the strongest currently available area field
# ---------------------------------------------------------

work = df[
    [
        "property_id",
        "listing_id",
        "source_city",
        "source_file",
        "city",
        "locality",
        "price_inr",
        "price_per_sqft",
        "area_sqft"
    ]
].dropna(
    subset=[
        "price_inr",
        "price_per_sqft",
        "area_sqft"
    ]
).copy()

work = work[
    (work["price_inr"] > 0)
    &
    (work["price_per_sqft"] > 0)
    &
    (work["area_sqft"] > 0)
]

# ---------------------------------------------------------
# Calculate our own price per sqft
# ---------------------------------------------------------

work["calculated_ppsf"] = (
    work["price_inr"] /
    work["area_sqft"]
)

work["difference_pct"] = (
    abs(
        work["calculated_ppsf"] -
        work["price_per_sqft"]
    )
    /
    work["price_per_sqft"]
) * 100

# ---------------------------------------------------------
# Classification
# ---------------------------------------------------------

work["ppsf_match_class"] = "MATCH"

work.loc[
    work["difference_pct"] > 5,
    "ppsf_match_class"
] = "MISMATCH"

# ---------------------------------------------------------
# Overall
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("OVERALL")
print("-" * 75)

total = len(work)

match = (
    work["difference_pct"] <= 5
).sum()

mismatch = total - match

print(
    f"Total comparable rows : {total:,}"
)

print(
    f"Within 5%             : "
    f"{match:,} "
    f"({match / total * 100:.2f}%)"
)

print(
    f"Over 5% difference     : "
    f"{mismatch:,} "
    f"({mismatch / total * 100:.2f}%)"
)

# ---------------------------------------------------------
# Mismatch by source city
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("MISMATCHES BY SOURCE CITY")
print("-" * 75)

city_summary = (
    work
    .groupby("source_city")
    .agg(
        total_rows=("property_id", "count"),
        mismatch_rows=(
            "ppsf_match_class",
            lambda x: (x == "MISMATCH").sum()
        )
    )
)

city_summary["mismatch_pct"] = (
    city_summary["mismatch_rows"]
    /
    city_summary["total_rows"]
    *
    100
)

city_summary = city_summary.sort_values(
    "mismatch_pct",
    ascending=False
)

print(
    city_summary.to_string()
)

# ---------------------------------------------------------
# Mismatch by source file
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("MISMATCHES BY SOURCE FILE")
print("-" * 75)

file_summary = (
    work
    .groupby("source_file")
    .agg(
        total_rows=("property_id", "count"),
        mismatch_rows=(
            "ppsf_match_class",
            lambda x: (x == "MISMATCH").sum()
        )
    )
)

file_summary["mismatch_pct"] = (
    file_summary["mismatch_rows"]
    /
    file_summary["total_rows"]
    *
    100
)

print(
    file_summary
    .sort_values(
        "mismatch_pct",
        ascending=False
    )
    .to_string()
)

# ---------------------------------------------------------
# Look at mismatch size
# ---------------------------------------------------------

mismatches = work[
    work["difference_pct"] > 5
].copy()

print("\n" + "-" * 75)
print("MISMATCH SIZE")
print("-" * 75)

if len(mismatches) > 0:

    print(
        mismatches["difference_pct"]
        .describe()
        .to_string()
    )

# ---------------------------------------------------------
# Representative examples
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
    "price_inr",
    "area_sqft",
    "calculated_ppsf",
    "price_per_sqft",
    "difference_pct"
]

print(
    mismatches[
        display_cols
    ]
    .sort_values(
        "difference_pct",
        ascending=False
    )
    .head(30)
    .to_string(index=False)
)

# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

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
print("PRICE/SQFT MISMATCH INVESTIGATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")
