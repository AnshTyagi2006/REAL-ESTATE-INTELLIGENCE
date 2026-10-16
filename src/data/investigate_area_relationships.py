from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# REAL ESTATE INTELLIGENCE PLATFORM
# AREA RELATIONSHIP INVESTIGATION
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

OUTPUT_FILE = (
    OUTPUT_DIR
    / "area_relationship_details.csv"
)


print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("AREA RELATIONSHIP INVESTIGATION")
print("=" * 75)


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print("\nReading Master V2...")
print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")


# ============================================================
# 1. FIELD OVERLAP
# ============================================================

print("\n" + "-" * 75)
print("AREA FIELD OVERLAP")
print("-" * 75)

fields = [
    "area_sqft",
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft",
    "carpet_area_sqft",
    "builtup_area_sqft",
    "superbuiltup_area_sqft",
]

fields = [
    f for f in fields
    if f in df.columns
]


for field_a in fields:

    for field_b in fields:

        if field_a >= field_b:
            continue

        overlap = (
            df[field_a].notna()
            &
            df[field_b].notna()
        ).sum()

        print(
            f"{field_a:<25} + "
            f"{field_b:<25} : "
            f"{overlap:,}"
        )


# ============================================================
# 2. AREA_MODEL VS MIN/MAX
# ============================================================

print("\n" + "-" * 75)
print("AREA_SQFT_MODEL VS AREA RANGE")
print("-" * 75)

if {
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft"
}.issubset(df.columns):

    mask = (
        df["area_sqft_model"].notna()
        &
        df["area_min_sqft"].notna()
        &
        df["area_max_sqft"].notna()
    )

    subset = df.loc[
        mask,
        [
            "property_id",
            "listing_id",
            "city",
            "locality",
            "area_sqft_model",
            "area_min_sqft",
            "area_max_sqft",
        ]
    ].copy()

    print(
        f"Rows with all three fields : "
        f"{len(subset):,}"
    )

    if len(subset) > 0:

        subset["range_width"] = (
            subset["area_max_sqft"]
            -
            subset["area_min_sqft"]
        )

        subset["model_minus_min"] = (
            subset["area_sqft_model"]
            -
            subset["area_min_sqft"]
        )

        subset["max_minus_model"] = (
            subset["area_max_sqft"]
            -
            subset["area_sqft_model"]
        )

        subset["model_inside_range"] = (
            (
                subset["area_sqft_model"]
                >=
                subset["area_min_sqft"]
            )
            &
            (
                subset["area_sqft_model"]
                <=
                subset["area_max_sqft"]
            )
        )

        inside_count = (
            subset["model_inside_range"]
            .sum()
        )

        print(
            f"Model inside min/max range : "
            f"{inside_count:,} "
            f"({inside_count / len(subset) * 100:.2f}%)"
        )

        # Is model equal to min?
        model_equals_min = np.isclose(
            subset["area_sqft_model"],
            subset["area_min_sqft"],
            rtol=0.001,
            atol=0.01
        )

        # Is model equal to max?
        model_equals_max = np.isclose(
            subset["area_sqft_model"],
            subset["area_max_sqft"],
            rtol=0.001,
            atol=0.01
        )

        print(
            f"Model approximately equals MIN : "
            f"{model_equals_min.sum():,} "
            f"({model_equals_min.mean() * 100:.2f}%)"
        )

        print(
            f"Model approximately equals MAX : "
            f"{model_equals_max.sum():,} "
            f"({model_equals_max.mean() * 100:.2f}%)"
        )

        # Save detailed rows
        subset.to_csv(
            OUTPUT_FILE,
            index=False
        )

        print(
            f"\nDetailed output saved to:\n"
            f"{OUTPUT_FILE}"
        )


# ============================================================
# 3. SIMPLE AREA STATISTICS
# ============================================================

print("\n" + "-" * 75)
print("AREA FIELD STATISTICS")
print("-" * 75)

for field in fields:

    series = (
        pd.to_numeric(
            df[field],
            errors="coerce"
        )
        .dropna()
    )

    if len(series) == 0:
        continue

    print(
        f"\n{field}"
    )

    print(
        f"  count  : {len(series):,}"
    )

    print(
        f"  median : {series.median():,.2f}"
    )

    print(
        f"  mean   : {series.mean():,.2f}"
    )

    print(
        f"  min    : {series.min():,.2f}"
    )

    print(
        f"  max    : {series.max():,.2f}"
    )


# ============================================================
# 4. EXAMPLE ROWS
# ============================================================

print("\n" + "-" * 75)
print("EXAMPLES: AREA_SQFT_MODEL")
print("-" * 75)

if "area_sqft_model" in df.columns:

    example_columns = [
        "property_id",
        "listing_id",
        "city",
        "locality",
        "configuration",
        "area_sqft_model",
        "area_min_sqft",
        "area_max_sqft",
        "price_per_sqft",
    ]

    example_columns = [
        c for c in example_columns
        if c in df.columns
    ]

    examples = (
        df[
            df["area_sqft_model"].notna()
        ][example_columns]
        .head(20)
    )

    print(
        examples.to_string(index=False)
    )


print("\n" + "=" * 75)
print("AREA RELATIONSHIP INVESTIGATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")