from pathlib import Path
import json

import numpy as np
import pandas as pd


# =========================================================
# CONFIGURATION
# =========================================================

INPUT_PATH = Path(
    "data/modeling/valuation_modeling_dataset.csv"
)

OUTPUT_DIR = Path("data/valuation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_PROPERTY_ID = "RE-00000001"


# =========================================================
# LOAD DATA
# =========================================================

df = pd.read_csv(INPUT_PATH)


# =========================================================
# BASIC VALIDATION
# =========================================================

required_columns = [
    "property_id",
    "city",
    "locality",
    "valuation_area_sqft",
    "asking_price_inr",
    "bedrooms",
    "bathrooms",
]


missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]


if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


# =========================================================
# PREPARE MARKET DATA
# =========================================================

market = df[
    required_columns
].copy()


market = market.dropna(
    subset=[
        "city",
        "locality",
        "valuation_area_sqft",
        "asking_price_inr",
    ]
)


# Calculate asking price per square foot.
market["asking_price_per_sqft"] = (
    market["asking_price_inr"]
    / market["valuation_area_sqft"]
)


# Remove invalid mathematical values.
market = market[
    np.isfinite(
        market["asking_price_per_sqft"]
    )
]


market = market[
    market["asking_price_per_sqft"] > 0
]


# =========================================================
# TARGET PROPERTY
# =========================================================

target_rows = df[
    df["property_id"] == TARGET_PROPERTY_ID
]


if target_rows.empty:
    raise ValueError(
        f"Target property {TARGET_PROPERTY_ID} not found."
    )


target = target_rows.iloc[0]

target_city = target["city"]
target_locality = target["locality"]
target_bedrooms = target["bedrooms"]


print("=" * 90)
print("LOCALITY MARKET INTELLIGENCE")
print("=" * 90)

print(f"\nTarget Property : {TARGET_PROPERTY_ID}")
print(f"City            : {target_city}")
print(f"Locality        : {target_locality}")
print(f"Bedrooms        : {target_bedrooms}")


# =========================================================
# TARGET LOCALITY
# =========================================================

locality_data = market[
    (market["city"] == target_city)
    & (market["locality"] == target_locality)
].copy()


print(
    f"\nProperties in target locality: "
    f"{len(locality_data)}"
)


# =========================================================
# MARKET STATISTICS FUNCTION
# =========================================================

def calculate_market_statistics(data):

    if data.empty:
        return None

    ppsf = data[
        "asking_price_per_sqft"
    ]

    prices = data[
        "asking_price_inr"
    ]

    areas = data[
        "valuation_area_sqft"
    ]

    statistics = {

        "property_count":
            int(len(data)),

        "median_asking_price_inr":
            float(prices.median()),

        "mean_asking_price_inr":
            float(prices.mean()),

        "p25_asking_price_inr":
            float(prices.quantile(0.25)),

        "p75_asking_price_inr":
            float(prices.quantile(0.75)),

        "median_ppsf":
            float(ppsf.median()),

        "mean_ppsf":
            float(ppsf.mean()),

        "p25_ppsf":
            float(ppsf.quantile(0.25)),

        "p75_ppsf":
            float(ppsf.quantile(0.75)),

        "minimum_ppsf":
            float(ppsf.min()),

        "maximum_ppsf":
            float(ppsf.max()),

        "ppsf_std":
            float(ppsf.std()),

        "median_area_sqft":
            float(areas.median()),

        "mean_area_sqft":
            float(areas.mean()),
    }

    return statistics


# =========================================================
# TARGET LOCALITY STATISTICS
# =========================================================

locality_stats = calculate_market_statistics(
    locality_data
)


# =========================================================
# CITY STATISTICS
# =========================================================

city_data = market[
    market["city"] == target_city
].copy()


city_stats = calculate_market_statistics(
    city_data
)


# =========================================================
# BEDROOM-SPECIFIC LOCALITY STATISTICS
# =========================================================

bedroom_locality_data = locality_data[
    locality_data["bedrooms"] == target_bedrooms
].copy()


bedroom_locality_stats = (
    calculate_market_statistics(
        bedroom_locality_data
    )
)


# =========================================================
# BHK DISTRIBUTION
# =========================================================

bhk_distribution = (
    locality_data[
        "bedrooms"
    ]
    .value_counts(
        dropna=False
    )
    .sort_index()
)


# =========================================================
# MARKET DISPERSION
# =========================================================

if locality_stats is not None:

    median_ppsf = locality_stats[
        "median_ppsf"
    ]

    p25_ppsf = locality_stats[
        "p25_ppsf"
    ]

    p75_ppsf = locality_stats[
        "p75_ppsf"
    ]

    if median_ppsf > 0:

        locality_spread_pct = (
            (p75_ppsf - p25_ppsf)
            / median_ppsf
        ) * 100

    else:

        locality_spread_pct = None

else:

    locality_spread_pct = None


# =========================================================
# TARGET'S ASKING PRICE POSITION
# =========================================================

target_asking_price = target[
    "asking_price_inr"
]

target_area = target[
    "valuation_area_sqft"
]


if (
    pd.notna(target_asking_price)
    and pd.notna(target_area)
    and target_area > 0
):

    target_ppsf = (
        target_asking_price
        / target_area
    )

else:

    target_ppsf = None


if (
    target_ppsf is not None
    and locality_stats is not None
):

    locality_median_ppsf = (
        locality_stats["median_ppsf"]
    )

    target_vs_locality_pct = (
        (
            target_ppsf
            - locality_median_ppsf
        )
        / locality_median_ppsf
    ) * 100

else:

    target_vs_locality_pct = None


# =========================================================
# PRINT LOCALITY RESULTS
# =========================================================

print("\n" + "=" * 90)
print("TARGET LOCALITY MARKET")
print("=" * 90)


if locality_stats is None:

    print(
        "No usable locality market data."
    )

else:

    print(
        f"Properties analyzed        : "
        f"{locality_stats['property_count']}"
    )

    print(
        f"Median asking price        : "
        f"₹{locality_stats['median_asking_price_inr']:,.0f}"
    )

    print(
        f"Median ₹/sqft              : "
        f"₹{locality_stats['median_ppsf']:,.0f}"
    )

    print(
        f"Mean ₹/sqft                : "
        f"₹{locality_stats['mean_ppsf']:,.0f}"
    )

    print(
        f"25th percentile ₹/sqft    : "
        f"₹{locality_stats['p25_ppsf']:,.0f}"
    )

    print(
        f"75th percentile ₹/sqft    : "
        f"₹{locality_stats['p75_ppsf']:,.0f}"
    )

    print(
        f"Minimum ₹/sqft             : "
        f"₹{locality_stats['minimum_ppsf']:,.0f}"
    )

    print(
        f"Maximum ₹/sqft             : "
        f"₹{locality_stats['maximum_ppsf']:,.0f}"
    )

    print(
        f"₹/sqft standard deviation : "
        f"₹{locality_stats['ppsf_std']:,.0f}"
    )

    print(
        f"Median area                : "
        f"{locality_stats['median_area_sqft']:,.0f} sqft"
    )

    print(
        f"Market spread (P25-P75)   : "
        f"{locality_spread_pct:.2f}%"
    )


# =========================================================
# BEDROOM-SPECIFIC RESULTS
# =========================================================

print("\n" + "=" * 90)
print(
    f"{int(target_bedrooms)}-BHK MARKET IN TARGET LOCALITY"
)
print("=" * 90)


if bedroom_locality_stats is None:

    print(
        "No usable bedroom-specific data."
    )

else:

    print(
        f"Properties analyzed        : "
        f"{bedroom_locality_stats['property_count']}"
    )

    print(
        f"Median asking price        : "
        f"₹{bedroom_locality_stats['median_asking_price_inr']:,.0f}"
    )

    print(
        f"Median ₹/sqft              : "
        f"₹{bedroom_locality_stats['median_ppsf']:,.0f}"
    )

    print(
        f"25th percentile ₹/sqft    : "
        f"₹{bedroom_locality_stats['p25_ppsf']:,.0f}"
    )

    print(
        f"75th percentile ₹/sqft    : "
        f"₹{bedroom_locality_stats['p75_ppsf']:,.0f}"
    )


# =========================================================
# CITY COMPARISON
# =========================================================

print("\n" + "=" * 90)
print("CITY-LEVEL MARKET")
print("=" * 90)


if city_stats is not None:

    print(
        f"Properties analyzed        : "
        f"{city_stats['property_count']}"
    )

    print(
        f"City median ₹/sqft        : "
        f"₹{city_stats['median_ppsf']:,.0f}"
    )

    print(
        f"City 25th percentile      : "
        f"₹{city_stats['p25_ppsf']:,.0f}"
    )

    print(
        f"City 75th percentile      : "
        f"₹{city_stats['p75_ppsf']:,.0f}"
    )


# =========================================================
# TARGET POSITION
# =========================================================

print("\n" + "=" * 90)
print("TARGET ASKING-PRICE POSITION")
print("=" * 90)


if target_ppsf is None:

    print(
        "Target asking price is unavailable."
    )

else:

    print(
        f"Target asking price         : "
        f"₹{target_asking_price:,.0f}"
    )

    print(
        f"Target asking ₹/sqft        : "
        f"₹{target_ppsf:,.0f}"
    )

    if target_vs_locality_pct is not None:

        print(
            f"Vs locality median         : "
            f"{target_vs_locality_pct:+.2f}%"
        )


# =========================================================
# BHK DISTRIBUTION
# =========================================================

print("\n" + "=" * 90)
print("LOCALITY BHK DISTRIBUTION")
print("=" * 90)

for bhk, count in bhk_distribution.items():

    print(
        f"{bhk} BHK : {count}"
    )


# =========================================================
# SAVE LOCALITY DATA
# =========================================================

locality_output_path = (
    OUTPUT_DIR
    / "locality_market_statistics.csv"
)


locality_rows = []


for (city, locality), group in market.groupby(
    ["city", "locality"],
    dropna=False
):

    stats = calculate_market_statistics(
        group
    )

    if stats is None:
        continue

    locality_rows.append(
        {
            "city": city,
            "locality": locality,
            **stats,
        }
    )


locality_summary_df = pd.DataFrame(
    locality_rows
)


locality_summary_df.to_csv(
    locality_output_path,
    index=False
)


# =========================================================
# SAVE TARGET LOCALITY BHK DATA
# =========================================================

bhk_output_path = (
    OUTPUT_DIR
    / "target_locality_bhk_statistics.csv"
)


bhk_rows = []


for bhk, group in locality_data.groupby(
    "bedrooms",
    dropna=False
):

    stats = calculate_market_statistics(
        group
    )

    if stats is None:
        continue

    bhk_rows.append(
        {
            "city": target_city,
            "locality": target_locality,
            "bedrooms": bhk,
            **stats,
        }
    )


pd.DataFrame(
    bhk_rows
).to_csv(
    bhk_output_path,
    index=False
)


# =========================================================
# SAVE JSON SUMMARY
# =========================================================

summary = {

    "target_property_id":
        TARGET_PROPERTY_ID,

    "target_city":
        target_city,

    "target_locality":
        target_locality,

    "target_bedrooms":
        float(target_bedrooms)
        if pd.notna(target_bedrooms)
        else None,

    "target_ppsf":
        float(target_ppsf)
        if target_ppsf is not None
        else None,

    "target_vs_locality_median_pct":
        float(target_vs_locality_pct)
        if target_vs_locality_pct is not None
        else None,

    "locality_statistics":
        locality_stats,

    "bedroom_specific_statistics":
        bedroom_locality_stats,

    "city_statistics":
        city_stats,

    "locality_spread_pct":
        float(locality_spread_pct)
        if locality_spread_pct is not None
        else None,

    "bhk_distribution":
        {
            str(k): int(v)
            for k, v in bhk_distribution.items()
        },
}


json_output_path = (
    OUTPUT_DIR
    / "target_locality_market_intelligence.json"
)


with open(
    json_output_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        summary,
        f,
        indent=4
    )


# =========================================================
# FINAL
# =========================================================

print("\n" + "=" * 90)
print("FILES CREATED")
print("=" * 90)

print(locality_output_path)
print(bhk_output_path)
print(json_output_path)

print(
    "\nLocality market intelligence completed."
)