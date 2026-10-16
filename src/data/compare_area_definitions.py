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
    / "area_definition_comparison.csv"
)

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("AREA DEFINITION COMPARISON")
print("=" * 75)

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")

area_fields = [
    "area_sqft",
    "superbuiltup_area_sqft",
    "builtup_area_sqft",
    "carpet_area_sqft"
]

# ---------------------------------------------------------
# Pairwise comparisons
# ---------------------------------------------------------

pairs = [
    ("area_sqft", "superbuiltup_area_sqft"),
    ("area_sqft", "builtup_area_sqft"),
    ("area_sqft", "carpet_area_sqft"),
    ("superbuiltup_area_sqft", "builtup_area_sqft"),
    ("superbuiltup_area_sqft", "carpet_area_sqft"),
    ("builtup_area_sqft", "carpet_area_sqft"),
]

results = []

print("\n" + "-" * 75)
print("PAIRWISE AREA COMPARISON")
print("-" * 75)

for field_a, field_b in pairs:

    work = df[
        [field_a, field_b]
    ].dropna().copy()

    work = work[
        (work[field_a] > 0)
        &
        (work[field_b] > 0)
    ]

    if len(work) == 0:
        continue

    work["ratio"] = (
        work[field_a] /
        work[field_b]
    )

    work["difference_pct"] = (
        abs(
            work[field_a] -
            work[field_b]
        )
        /
        work[field_b]
    ) * 100

    within_1 = (
        work["difference_pct"] <= 1
    ).sum()

    within_5 = (
        work["difference_pct"] <= 5
    ).sum()

    within_10 = (
        work["difference_pct"] <= 10
    ).sum()

    print(f"\n{field_a}  VS  {field_b}")

    print(
        f"  Comparable rows : {len(work):,}"
    )

    print(
        f"  Median ratio    : "
        f"{work['ratio'].median():.4f}"
    )

    print(
        f"  Mean ratio      : "
        f"{work['ratio'].mean():.4f}"
    )

    print(
        f"  Within 1%       : "
        f"{within_1:,} "
        f"({within_1 / len(work) * 100:.2f}%)"
    )

    print(
        f"  Within 5%       : "
        f"{within_5:,} "
        f"({within_5 / len(work) * 100:.2f}%)"
    )

    print(
        f"  Within 10%      : "
        f"{within_10:,} "
        f"({within_10 / len(work) * 100:.2f}%)"
    )

    results.append({
        "field_a": field_a,
        "field_b": field_b,
        "comparable_rows": len(work),
        "median_ratio": work["ratio"].median(),
        "mean_ratio": work["ratio"].mean(),
        "within_1_pct": within_1,
        "within_1_pct_rate": (
            within_1 / len(work) * 100
        ),
        "within_5_pct": within_5,
        "within_5_pct_rate": (
            within_5 / len(work) * 100
        ),
        "within_10_pct": within_10,
        "within_10_pct_rate": (
            within_10 / len(work) * 100
        )
    })

# ---------------------------------------------------------
# Save summary
# ---------------------------------------------------------

summary = pd.DataFrame(results)

summary.to_csv(
    OUTPUT_FILE,
    index=False
)

# ---------------------------------------------------------
# Detailed source-city comparison
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("AREA RELATIONSHIPS BY SOURCE CITY")
print("-" * 75)

city_pairs = [
    ("area_sqft", "superbuiltup_area_sqft"),
    ("area_sqft", "builtup_area_sqft"),
    ("area_sqft", "carpet_area_sqft"),
]

for field_a, field_b in city_pairs:

    work = df[
        [
            "source_city",
            field_a,
            field_b
        ]
    ].dropna().copy()

    work = work[
        (work[field_a] > 0)
        &
        (work[field_b] > 0)
    ]

    if len(work) == 0:
        continue

    work["ratio"] = (
        work[field_a] /
        work[field_b]
    )

    work["difference_pct"] = (
        abs(
            work[field_a] -
            work[field_b]
        )
        /
        work[field_b]
    ) * 100

    city_summary = (
        work
        .groupby("source_city")
        .agg(
            comparable_rows=("ratio", "count"),
            median_ratio=("ratio", "median"),
            mean_ratio=("ratio", "mean"),
            within_5_pct=(
                "difference_pct",
                lambda x: (
                    x <= 5
                ).sum()
            )
        )
        .reset_index()
    )

    city_summary["within_5_pct_rate"] = (
        city_summary["within_5_pct"]
        /
        city_summary["comparable_rows"]
        *
        100
    )

    print(
        f"\n{field_a}  VS  {field_b}"
    )

    print(
        city_summary
        .sort_values(
            "comparable_rows",
            ascending=False
        )
        .to_string(index=False)
    )

# ---------------------------------------------------------
# Show representative examples
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("REPRESENTATIVE OVERLAPPING RECORDS")
print("-" * 75)

example_cols = [
    "property_id",
    "listing_id",
    "source_city",
    "city",
    "locality",
    "area_sqft",
    "superbuiltup_area_sqft",
    "builtup_area_sqft",
    "carpet_area_sqft"
]

examples = df[
    example_cols
].dropna(
    subset=["area_sqft"]
)

print(
    examples.head(30).to_string(index=False)
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("AREA DEFINITION COMPARISON COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")