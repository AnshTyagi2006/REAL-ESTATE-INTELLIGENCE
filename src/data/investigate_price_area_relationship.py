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
    / "price_area_relationship.csv"
)

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("PRICE / AREA RELATIONSHIP INVESTIGATION")
print("=" * 75)

df = pd.read_csv(INPUT_FILE, low_memory=False)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")

# ---------------------------------------------------------
# Candidate area fields
# ---------------------------------------------------------

area_fields = [
    "area_sqft",
    "area_sqft_model",
    "carpet_area_sqft",
    "builtup_area_sqft",
    "superbuiltup_area_sqft"
]

# ---------------------------------------------------------
# Keep rows with price + price per sqft
# ---------------------------------------------------------

work = df[
    [
        "property_id",
        "listing_id",
        "source_city",
        "city",
        "locality",
        "price_inr",
        "price_per_sqft"
    ] + area_fields
].copy()

work = work.dropna(
    subset=[
        "price_inr",
        "price_per_sqft"
    ]
)

print("\n" + "-" * 75)
print("BASE DATA")
print("-" * 75)

print(
    f"Rows with price + price_per_sqft : {len(work):,}"
)

# ---------------------------------------------------------
# Calculate implied price/sqft for each area definition
# ---------------------------------------------------------

results = []

for area in area_fields:

    subset = work.dropna(
        subset=[area]
    ).copy()

    subset = subset[
        subset[area] > 0
    ]

    if len(subset) == 0:
        continue

    subset["calculated_ppsf"] = (
        subset["price_inr"] /
        subset[area]
    )

    subset["difference_pct"] = (
        abs(
            subset["calculated_ppsf"] -
            subset["price_per_sqft"]
        )
        /
        subset["price_per_sqft"]
    ) * 100

    for tolerance in [1, 5, 10]:

        matching = (
            subset["difference_pct"] <= tolerance
        ).sum()

        results.append({
            "area_field": area,
            "rows_comparable": len(subset),
            "tolerance_pct": tolerance,
            "matching_rows": matching,
            "matching_pct": (
                matching /
                len(subset) *
                100
            )
        })

# ---------------------------------------------------------
# Print summary
# ---------------------------------------------------------

summary = pd.DataFrame(results)

print("\n" + "-" * 75)
print("PRICE/SQFT CONSISTENCY")
print("-" * 75)

for area in area_fields:

    temp = summary[
        summary["area_field"] == area
    ]

    if len(temp) == 0:
        continue

    print(f"\n{area}")

    for _, row in temp.iterrows():

        print(
            f"  Within {int(row['tolerance_pct'])}% : "
            f"{int(row['matching_rows']):,} / "
            f"{int(row['rows_comparable']):,} "
            f"({row['matching_pct']:.2f}%)"
        )

# ---------------------------------------------------------
# Detailed comparison at 5%
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("BEST MATCHING AREA FIELD")
print("-" * 75)

best = (
    summary[
        summary["tolerance_pct"] == 5
    ]
    .sort_values(
        "matching_pct",
        ascending=False
    )
)

print(
    best[
        [
            "area_field",
            "rows_comparable",
            "matching_rows",
            "matching_pct"
        ]
    ].to_string(index=False)
)

# ---------------------------------------------------------
# Save summary
# ---------------------------------------------------------

summary.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("PRICE / AREA RELATIONSHIP INVESTIGATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")