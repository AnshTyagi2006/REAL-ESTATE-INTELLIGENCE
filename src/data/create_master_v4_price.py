from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v3.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v4.csv"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "data"
    / "validation"
    / "master_v4_price_report.csv"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("MASTER V4 - CANONICAL PRICE LAYER")
print("=" * 75)


# ============================================================
# LOAD MASTER V3
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows before : {len(df):,}")
print(f"Columns     : {len(df.columns):,}")


# ============================================================
# REQUIRED FIELD CHECK
# ============================================================

required_columns = [
    "price_inr",
    "price_min_inr",
    "price_max_inr",
]

missing_columns = [
    col
    for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Required columns are missing: {missing_columns}"
    )


# ============================================================
# NUMERIC CONVERSION
# ============================================================

for col in required_columns:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )


# ============================================================
# PRICE MASKS
# ============================================================

# Exact price available directly
direct_price_mask = (
    df["price_inr"].notna()
    & (df["price_inr"] > 0)
)


# Exact price represented through min/max
# Only accept it when both exist, are positive,
# and min == max.
min_max_price_mask = (
    ~direct_price_mask
    & df["price_min_inr"].notna()
    & df["price_max_inr"].notna()
    & (df["price_min_inr"] > 0)
    & (df["price_max_inr"] > 0)
    & (
        df["price_min_inr"]
        == df["price_max_inr"]
    )
)


# ============================================================
# CREATE CANONICAL ASKING PRICE
# ============================================================

df["asking_price_inr"] = np.nan

df.loc[
    direct_price_mask,
    "asking_price_inr"
] = df.loc[
    direct_price_mask,
    "price_inr"
]


df.loc[
    min_max_price_mask,
    "asking_price_inr"
] = df.loc[
    min_max_price_mask,
    "price_min_inr"
]


# ============================================================
# PRICE SOURCE
# ============================================================

df["asking_price_source"] = "UNAVAILABLE"

df.loc[
    direct_price_mask,
    "asking_price_source"
] = "PRICE_INR"


df.loc[
    min_max_price_mask,
    "asking_price_source"
] = "PRICE_MIN_MAX"


# ============================================================
# PRICE QUALITY
# ============================================================

df["asking_price_quality"] = "UNAVAILABLE"

df.loc[
    direct_price_mask,
    "asking_price_quality"
] = "DIRECT"


df.loc[
    min_max_price_mask,
    "asking_price_quality"
] = "DIRECT"


# ============================================================
# VALIDATION COUNTS
# ============================================================

total_rows = len(df)

direct_count = int(
    direct_price_mask.sum()
)

min_max_count = int(
    min_max_price_mask.sum()
)

unavailable_count = int(
    df["asking_price_inr"].isna().sum()
)

available_count = int(
    df["asking_price_inr"].notna().sum()
)


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n" + "-" * 75)
print("CANONICAL PRICE SOURCE")
print("-" * 75)

print(
    df["asking_price_source"]
    .value_counts(dropna=False)
    .to_string()
)


print("\n" + "-" * 75)
print("CANONICAL PRICE QUALITY")
print("-" * 75)

print(
    df["asking_price_quality"]
    .value_counts(dropna=False)
    .to_string()
)


print("\n" + "-" * 75)
print("ASKING PRICE AVAILABILITY")
print("-" * 75)

print(
    f"Available asking price : "
    f"{available_count:,} / {total_rows:,} "
    f"({available_count / total_rows * 100:.2f}%)"
)

print(
    f"Unavailable            : "
    f"{unavailable_count:,} / {total_rows:,} "
    f"({unavailable_count / total_rows * 100:.2f}%)"
)


print("\n" + "-" * 75)
print("PRICE SOURCE BREAKDOWN")
print("-" * 75)

print(
    f"Direct price_inr       : "
    f"{direct_count:,}"
)

print(
    f"Min/max exact price    : "
    f"{min_max_count:,}"
)


# ============================================================
# CANONICAL PRICE VALIDATION
# ============================================================

print("\n" + "-" * 75)
print("CANONICAL PRICE VALIDATION")
print("-" * 75)


# Every canonical price must be positive
invalid_canonical_price = int(
    (
        df["asking_price_inr"].notna()
        &
        (df["asking_price_inr"] <= 0)
    ).sum()
)

print(
    f"Invalid canonical prices : "
    f"{invalid_canonical_price}"
)


# Direct price must equal price_inr
direct_mismatch = int(
    (
        direct_price_mask
        &
        (
            df["asking_price_inr"]
            != df["price_inr"]
        )
    ).sum()
)

print(
    f"Direct price mismatches   : "
    f"{direct_mismatch}"
)


# Min/max derived price must equal both min and max
minmax_mismatch = int(
    (
        min_max_price_mask
        &
        (
            (
                df["asking_price_inr"]
                != df["price_min_inr"]
            )
            |
            (
                df["asking_price_inr"]
                != df["price_max_inr"]
            )
        )
    ).sum()
)

print(
    f"Min/max price mismatches  : "
    f"{minmax_mismatch}"
)


# ============================================================
# PRICE STATISTICS
# ============================================================

print("\n" + "-" * 75)
print("CANONICAL ASKING PRICE STATISTICS")
print("-" * 75)

valid_prices = df.loc[
    df["asking_price_inr"].notna(),
    "asking_price_inr"
]

if len(valid_prices) > 0:

    print(
        f"Count  : {len(valid_prices):,}"
    )

    print(
        f"Min    : ₹{valid_prices.min():,.2f}"
    )

    print(
        f"Median : ₹{valid_prices.median():,.2f}"
    )

    print(
        f"Mean   : ₹{valid_prices.mean():,.2f}"
    )

    print(
        f"Max    : ₹{valid_prices.max():,.2f}"
    )


# ============================================================
# SOURCE CITY BREAKDOWN
# ============================================================

print("\n" + "-" * 75)
print("CANONICAL PRICE BY SOURCE CITY")
print("-" * 75)

city_rows = []

for source_city, group in df.groupby(
    "source_city",
    dropna=False
):

    total = len(group)

    available = int(
        group["asking_price_inr"]
        .notna()
        .sum()
    )

    direct = int(
        (
            group["asking_price_source"]
            == "PRICE_INR"
        ).sum()
    )

    min_max = int(
        (
            group["asking_price_source"]
            == "PRICE_MIN_MAX"
        ).sum()
    )

    city_rows.append({
        "source_city": source_city,
        "rows": total,
        "asking_price_available": available,
        "asking_price_pct": round(
            available / total * 100,
            2
        ),
        "price_inr_source": direct,
        "price_min_max_source": min_max,
    })


city_summary = pd.DataFrame(city_rows)

city_summary = city_summary.sort_values(
    "rows",
    ascending=False
)

print(
    city_summary.to_string(
        index=False
    )
)


# ============================================================
# REPORT
# ============================================================

report_rows = [
    {
        "metric": "rows_before",
        "value": total_rows
    },
    {
        "metric": "rows_after",
        "value": len(df)
    },
    {
        "metric": "direct_price_count",
        "value": direct_count
    },
    {
        "metric": "min_max_price_count",
        "value": min_max_count
    },
    {
        "metric": "asking_price_available",
        "value": available_count
    },
    {
        "metric": "asking_price_unavailable",
        "value": unavailable_count
    },
    {
        "metric": "invalid_canonical_price",
        "value": invalid_canonical_price
    },
    {
        "metric": "direct_price_mismatches",
        "value": direct_mismatch
    },
    {
        "metric": "min_max_price_mismatches",
        "value": minmax_mismatch
    },
]


report_df = pd.DataFrame(
    report_rows
)


# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

REPORT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SAVE MASTER V4
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SAVE VALIDATION REPORT
# ============================================================

report_df.to_csv(
    REPORT_FILE,
    index=False
)


# ============================================================
# FINAL
# ============================================================

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print(
    f"Master V4:\n{OUTPUT_FILE}"
)

print(
    f"\nPrice report:\n{REPORT_FILE}"
)

print("\n" + "=" * 75)
print("MASTER V4 PRICE LAYER CREATION COMPLETE")
print("=" * 75)

print("\nMaster V3 was NOT modified.")