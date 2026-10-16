from pathlib import Path
import json
import numpy as np
import pandas as pd


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

OUTPUT_DIR = PROJECT_ROOT / "data" / "investigation"
OUTPUT_FILE = OUTPUT_DIR / "price_field_investigation.json"


# ============================================================
# HELPERS
# ============================================================

def numeric(series):
    """
    Safely convert a pandas Series to numeric.
    Invalid values become NaN.
    """
    return pd.to_numeric(series, errors="coerce")


def percentage(value, total):
    """
    Return percentage safely.
    """
    if total == 0:
        return 0.0

    return round((value / total) * 100, 2)


def describe_numeric(series):
    """
    Return useful statistics for a numeric field.
    """
    s = numeric(series).dropna()

    if len(s) == 0:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "mean": None,
            "max": None,
        }

    return {
        "count": int(len(s)),
        "min": float(s.min()),
        "median": float(s.median()),
        "mean": float(s.mean()),
        "max": float(s.max()),
    }


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("PRICE FIELD INVESTIGATION")
print("=" * 75)

print(f"Input file : {INPUT_FILE}")

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Rows       : {len(df):,}")
print(f"Columns    : {len(df):,}")


# ============================================================
# REQUIRED FIELDS
# ============================================================

price_fields = [
    "price_inr",
    "price_lakh",
    "price_crore",
    "price_min_inr",
    "price_max_inr",
    "price_per_sqft",
]

missing_fields = [
    col for col in price_fields
    if col not in df.columns
]

if missing_fields:
    raise ValueError(
        f"Required price fields missing: {missing_fields}"
    )


# Convert relevant fields to numeric
for col in price_fields:
    df[col] = numeric(df[col])


# ============================================================
# 1. PRICE FIELD AVAILABILITY
# ============================================================

print("\n" + "-" * 75)
print("PRICE FIELD AVAILABILITY")
print("-" * 75)

availability = {}

for col in price_fields:
    count = int(df[col].notna().sum())

    availability[col] = {
        "count": count,
        "percentage": percentage(count, len(df)),
    }

    print(
        f"{col:<20} "
        f"{count:>6,} "
        f"({percentage(count, len(df)):>6.2f}%)"
    )


# ============================================================
# 2. PRICE REPRESENTATION CONSISTENCY
# ============================================================

print("\n" + "-" * 75)
print("PRICE REPRESENTATION CONSISTENCY")
print("-" * 75)


# ------------------------------------------------------------
# INR vs LAKH
# ------------------------------------------------------------

mask = (
    df["price_inr"].notna()
    & df["price_lakh"].notna()
    & (df["price_inr"] > 0)
    & (df["price_lakh"] > 0)
)

if mask.any():

    expected_lakh = df.loc[mask, "price_inr"] / 100_000

    difference_pct = (
        (df.loc[mask, "price_lakh"] - expected_lakh)
        .abs()
        / expected_lakh
        * 100
    )

    within_1 = int((difference_pct <= 1).sum())
    within_5 = int((difference_pct <= 5).sum())

    print(
        f"INR vs Lakh:"
        f" {mask.sum():,} comparable"
    )

    print(
        f"  Within 1% : {within_1:,} "
        f"({percentage(within_1, mask.sum()):.2f}%)"
    )

    print(
        f"  Within 5% : {within_5:,} "
        f"({percentage(within_5, mask.sum()):.2f}%)"
    )

    inr_lakh_consistency = {
        "comparable": int(mask.sum()),
        "within_1_percent": within_1,
        "within_5_percent": within_5,
    }

else:

    inr_lakh_consistency = {
        "comparable": 0,
        "within_1_percent": 0,
        "within_5_percent": 0,
    }


# ------------------------------------------------------------
# INR vs CRORE
# ------------------------------------------------------------

mask = (
    df["price_inr"].notna()
    & df["price_crore"].notna()
    & (df["price_inr"] > 0)
    & (df["price_crore"] > 0)
)

if mask.any():

    expected_crore = df.loc[mask, "price_inr"] / 10_000_000

    difference_pct = (
        (df.loc[mask, "price_crore"] - expected_crore)
        .abs()
        / expected_crore
        * 100
    )

    within_1 = int((difference_pct <= 1).sum())
    within_5 = int((difference_pct <= 5).sum())

    print(
        f"\nINR vs Crore:"
        f" {mask.sum():,} comparable"
    )

    print(
        f"  Within 1% : {within_1:,} "
        f"({percentage(within_1, mask.sum()):.2f}%)"
    )

    print(
        f"  Within 5% : {within_5:,} "
        f"({percentage(within_5, mask.sum()):.2f}%)"
    )

    inr_crore_consistency = {
        "comparable": int(mask.sum()),
        "within_1_percent": within_1,
        "within_5_percent": within_5,
    }

else:

    inr_crore_consistency = {
        "comparable": 0,
        "within_1_percent": 0,
        "within_5_percent": 0,
    }


# ============================================================
# 3. PRICE RANGE VALIDITY
# ============================================================

print("\n" + "-" * 75)
print("PRICE RANGE VALIDITY")
print("-" * 75)

range_mask = (
    df["price_min_inr"].notna()
    & df["price_max_inr"].notna()
)

range_count = int(range_mask.sum())

invalid_range = int(
    (
        df.loc[range_mask, "price_min_inr"]
        > df.loc[range_mask, "price_max_inr"]
    ).sum()
)

equal_range = int(
    (
        df.loc[range_mask, "price_min_inr"]
        == df.loc[range_mask, "price_max_inr"]
    ).sum()
)

proper_range = int(
    (
        df.loc[range_mask, "price_min_inr"]
        < df.loc[range_mask, "price_max_inr"]
    ).sum()
)

print(f"Comparable ranges : {range_count:,}")

print(
    f"Valid min < max   : {proper_range:,} "
    f"({percentage(proper_range, range_count):.2f}%)"
)

print(
    f"Equal min = max   : {equal_range:,} "
    f"({percentage(equal_range, range_count):.2f}%)"
)

print(
    f"Invalid min > max : {invalid_range:,} "
    f"({percentage(invalid_range, range_count):.2f}%)"
)


# ============================================================
# 4. DOES EXACT PRICE FALL INSIDE THE RANGE?
# ============================================================

print("\n" + "-" * 75)
print("EXACT PRICE VS PRICE RANGE")
print("-" * 75)

range_price_mask = (
    df["price_inr"].notna()
    & df["price_min_inr"].notna()
    & df["price_max_inr"].notna()
    & (df["price_min_inr"] <= df["price_max_inr"])
)

inside = (
    (df.loc[range_price_mask, "price_inr"]
     >= df.loc[range_price_mask, "price_min_inr"])
    &
    (df.loc[range_price_mask, "price_inr"]
     <= df.loc[range_price_mask, "price_max_inr"])
)

inside_count = int(inside.sum())
outside_count = int((~inside).sum())

print(
    f"Exact price + valid range : "
    f"{range_price_mask.sum():,}"
)

print(
    f"Price inside range        : "
    f"{inside_count:,} "
    f"({percentage(inside_count, range_price_mask.sum()):.2f}%)"
)

print(
    f"Price outside range       : "
    f"{outside_count:,} "
    f"({percentage(outside_count, range_price_mask.sum()):.2f}%)"
)


# ============================================================
# 5. PRICE RANGE WIDTH
# ============================================================

print("\n" + "-" * 75)
print("PRICE RANGE WIDTH")
print("-" * 75)

valid_range = (
    range_mask
    & (df["price_min_inr"] > 0)
    & (df["price_max_inr"] >= df["price_min_inr"])
)

if valid_range.any():

    range_width_pct = (
        (
            df.loc[valid_range, "price_max_inr"]
            - df.loc[valid_range, "price_min_inr"]
        )
        / df.loc[valid_range, "price_min_inr"]
        * 100
    )

    print(
        f"Valid ranges : {valid_range.sum():,}"
    )

    print(
        f"Median width : "
        f"{range_width_pct.median():.2f}%"
    )

    print(
        f"Mean width   : "
        f"{range_width_pct.mean():.2f}%"
    )

    print(
        f"Maximum width: "
        f"{range_width_pct.max():.2f}%"
    )

    range_width_summary = {
        "count": int(len(range_width_pct)),
        "median_percent": float(range_width_pct.median()),
        "mean_percent": float(range_width_pct.mean()),
        "max_percent": float(range_width_pct.max()),
    }

else:

    range_width_summary = {
        "count": 0,
        "median_percent": None,
        "mean_percent": None,
        "max_percent": None,
    }


# ============================================================
# 6. PRICE STATISTICS
# ============================================================

print("\n" + "-" * 75)
print("PRICE STATISTICS")
print("-" * 75)

price_statistics = {}

for col in [
    "price_inr",
    "price_lakh",
    "price_crore",
    "price_min_inr",
    "price_max_inr",
]:
    stats = describe_numeric(df[col])
    price_statistics[col] = stats

    print(f"\n{col}")

    if stats["count"] == 0:
        print("  No values")
        continue

    print(f"  Count  : {stats['count']:,}")
    print(f"  Min    : {stats['min']:,.2f}")
    print(f"  Median : {stats['median']:,.2f}")
    print(f"  Mean   : {stats['mean']:,.2f}")
    print(f"  Max    : {stats['max']:,.2f}")


# ============================================================
# 7. PRICE AVAILABILITY BY SOURCE CITY
# ============================================================

print("\n" + "-" * 75)
print("PRICE AVAILABILITY BY SOURCE CITY")
print("-" * 75)

city_summary = []

for source_city, group in df.groupby(
    "source_city",
    dropna=False
):

    total = len(group)

    price_count = int(
        group["price_inr"].notna().sum()
    )

    minmax_count = int(
        (
            group["price_min_inr"].notna()
            & group["price_max_inr"].notna()
        ).sum()
    )

    area_count = int(
        group["valuation_area_sqft"].notna().sum()
    )

    city_summary.append({
        "source_city": source_city,
        "rows": total,
        "price_inr_count": price_count,
        "price_inr_pct": percentage(price_count, total),
        "price_range_count": minmax_count,
        "price_range_pct": percentage(minmax_count, total),
        "valuation_area_count": area_count,
        "valuation_area_pct": percentage(area_count, total),
    })

city_summary_df = pd.DataFrame(city_summary)

city_summary_df = city_summary_df.sort_values(
    "rows",
    ascending=False
)

print(
    city_summary_df.to_string(index=False)
)


# ============================================================
# 8. EXTREME PRICE INVESTIGATION
# ============================================================

print("\n" + "-" * 75)
print("EXTREME PRICE VALUES")
print("-" * 75)

valid_price = df[
    df["price_inr"].notna()
    & (df["price_inr"] > 0)
].copy()

if len(valid_price) > 0:

    extreme_columns = [
        "property_id",
        "listing_id",
        "source_city",
        "city",
        "locality",
        "property_type",
        "configuration",
        "bedrooms",
        "valuation_area_sqft",
        "price_inr",
        "price_lakh",
        "price_crore",
        "price_min_inr",
        "price_max_inr",
        "price_per_sqft",
    ]

    extreme_columns = [
        col for col in extreme_columns
        if col in valid_price.columns
    ]

    highest_prices = (
        valid_price
        .sort_values("price_inr", ascending=False)
        [extreme_columns]
        .head(20)
    )

    print("\nTop 20 highest exact prices:")

    print(
        highest_prices.to_string(index=False)
    )

else:

    highest_prices = pd.DataFrame()


# ============================================================
# 9. ZERO / NEGATIVE PRICE CHECK
# ============================================================

print("\n" + "-" * 75)
print("INVALID PRICE CHECK")
print("-" * 75)

invalid_price_counts = {}

for col in [
    "price_inr",
    "price_min_inr",
    "price_max_inr",
    "price_per_sqft",
]:

    zero_count = int(
        (df[col] == 0).sum()
    )

    negative_count = int(
        (df[col] < 0).sum()
    )

    invalid_price_counts[col] = {
        "zero": zero_count,
        "negative": negative_count,
    }

    print(
        f"{col:<20}"
        f" zero={zero_count:<6}"
        f" negative={negative_count}"
    )


# ============================================================
# 10. SAVE INVESTIGATION REPORT
# ============================================================

report = {
    "dataset": {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
    },

    "availability": availability,

    "representation_consistency": {
        "inr_vs_lakh": inr_lakh_consistency,
        "inr_vs_crore": inr_crore_consistency,
    },

    "range_validation": {
        "comparable": range_count,
        "valid_min_less_than_max": proper_range,
        "equal_min_max": equal_range,
        "invalid_min_greater_than_max": invalid_range,
    },

    "exact_price_vs_range": {
        "comparable": int(range_price_mask.sum()),
        "inside_range": inside_count,
        "outside_range": outside_count,
    },

    "range_width": range_width_summary,

    "price_statistics": price_statistics,

    "invalid_price_values": invalid_price_counts,

    "source_city_summary": city_summary_df.to_dict(
        orient="records"
    ),

    "highest_prices": (
        highest_prices
        .replace({np.nan: None})
        .to_dict(orient="records")
        if not highest_prices.empty
        else []
    ),
}


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        report,
        f,
        indent=4,
        default=str
    )


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 75)
print("PRICE FIELD INVESTIGATION COMPLETE")
print("=" * 75)

print(
    f"\nInvestigation report:\n{OUTPUT_FILE}"
)

print("\nMaster V3 was NOT modified.")