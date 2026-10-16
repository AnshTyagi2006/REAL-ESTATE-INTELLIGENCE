from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

INPUT_PATH = Path(
    "data/modeling/valuation_modeling_dataset.csv"
)

OUTPUT_DIR = Path("data/valuation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Target property
# ---------------------------------------------------------

TARGET_PROPERTY_ID = "RE-00000001"


# ---------------------------------------------------------
# Load dataset
# ---------------------------------------------------------

df = pd.read_csv(INPUT_PATH)


# ---------------------------------------------------------
# Find target property
# ---------------------------------------------------------

target = df[df["property_id"] == TARGET_PROPERTY_ID].iloc[0]


target_city = target["city"]
target_locality = target["locality"]
target_area = target["valuation_area_sqft"]
target_bedrooms = target["bedrooms"]
target_bathrooms = target["bathrooms"]


print("=" * 80)
print("COMPARABLE PRICE ANALYSIS")
print("=" * 80)

print(f"\nTarget Property : {TARGET_PROPERTY_ID}")
print(f"City            : {target_city}")
print(f"Locality        : {target_locality}")
print(f"Area            : {target_area:,.2f} sqft")
print(f"Bedrooms        : {target_bedrooms}")
print(f"Bathrooms       : {target_bathrooms}")


# ---------------------------------------------------------
# Remove target itself
# ---------------------------------------------------------

candidates = df[
    (df["property_id"] != TARGET_PROPERTY_ID)
    & (df["city"] == target_city)
].copy()


# ---------------------------------------------------------
# Initial comparable filters
#
# Same city
# Area +/- 20%
# Bedrooms +/- 1
# Bathrooms +/- 1
# ---------------------------------------------------------

area_min = target_area * 0.80
area_max = target_area * 1.20

candidates = candidates[
    candidates["valuation_area_sqft"].between(
        area_min,
        area_max
    )
]

candidates = candidates[
    candidates["bedrooms"].between(
        target_bedrooms - 1,
        target_bedrooms + 1
    )
]

candidates = candidates[
    candidates["bathrooms"].between(
        target_bathrooms - 1,
        target_bathrooms + 1
    )
].copy()


# ---------------------------------------------------------
# Distance calculation
# ---------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate approximate distance between two coordinates
    using the Haversine formula.
    """

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    c = 2 * np.arctan2(
        np.sqrt(a),
        np.sqrt(1 - a)
    )

    return EARTH_RADIUS_KM * c


candidates["distance_km"] = haversine_distance(
    target["latitude"],
    target["longitude"],
    candidates["latitude"],
    candidates["longitude"]
)


# ---------------------------------------------------------
# Comparable similarity measures
# ---------------------------------------------------------

candidates["same_locality"] = (
    candidates["locality"] == target_locality
)


candidates["area_difference_pct"] = (
    abs(
        candidates["valuation_area_sqft"]
        - target_area
    )
    / target_area
) * 100


candidates["bedroom_difference"] = (
    abs(
        candidates["bedrooms"]
        - target_bedrooms
    )
)


candidates["bathroom_difference"] = (
    abs(
        candidates["bathrooms"]
        - target_bathrooms
    )
)


# ---------------------------------------------------------
# Calculate asking price per sqft
# ---------------------------------------------------------

candidates["asking_price_per_sqft"] = (
    candidates["asking_price_inr"]
    / candidates["valuation_area_sqft"]
)


# ---------------------------------------------------------
# Similarity score
# Same scoring logic used by the ranking step
# ---------------------------------------------------------

candidates["locality_score"] = np.where(
    candidates["same_locality"],
    1.0,
    0.0
)


candidates["distance_score"] = (
    1
    - candidates["distance_km"] / 5
).clip(0, 1)


candidates["area_score"] = (
    1
    - candidates["area_difference_pct"] / 20
).clip(0, 1)


candidates["bedroom_score"] = (
    1
    - candidates["bedroom_difference"]
).clip(0, 1)


candidates["bathroom_score"] = (
    1
    - candidates["bathroom_difference"]
).clip(0, 1)


# Property type score only when both are known
property_type_available = (
    target["property_type"] == target["property_type"]
) & (
    candidates["property_type"].notna()
)


candidates["property_type_score"] = np.where(
    property_type_available,
    (
        candidates["property_type"]
        == target["property_type"]
    ).astype(float),
    np.nan
)


# ---------------------------------------------------------
# Calculate normalized similarity score
# ---------------------------------------------------------

weights = {
    "locality_score": 0.30,
    "distance_score": 0.20,
    "area_score": 0.20,
    "bedroom_score": 0.10,
    "bathroom_score": 0.10,
    "property_type_score": 0.10,
}


weighted_sum = np.zeros(len(candidates))
weight_sum = np.zeros(len(candidates))


for column, weight in weights.items():

    available = candidates[column].notna()

    weighted_sum += (
        candidates[column].fillna(0)
        * weight
    )

    weight_sum += (
        available.astype(float)
        * weight
    )


candidates["similarity_score"] = (
    weighted_sum
    / weight_sum
) * 100


# ---------------------------------------------------------
# Sort by similarity
# ---------------------------------------------------------

candidates = candidates.sort_values(
    by="similarity_score",
    ascending=False
).reset_index(drop=True)


# ---------------------------------------------------------
# Price statistics helper
# ---------------------------------------------------------

def print_price_statistics(data, label):

    print("\n" + "-" * 80)
    print(label)
    print("-" * 80)

    if len(data) == 0:
        print("No comparable properties.")
        return

    ppsf = data["asking_price_per_sqft"]

    print(f"Comparable count : {len(data)}")

    print(
        f"Mean ₹/sqft     : ₹{ppsf.mean():,.0f}"
    )

    print(
        f"Median ₹/sqft   : ₹{ppsf.median():,.0f}"
    )

    print(
        f"25th percentile : ₹{ppsf.quantile(0.25):,.0f}"
    )

    print(
        f"75th percentile : ₹{ppsf.quantile(0.75):,.0f}"
    )

    print(
        f"Minimum ₹/sqft  : ₹{ppsf.min():,.0f}"
    )

    print(
        f"Maximum ₹/sqft  : ₹{ppsf.max():,.0f}"
    )

    print(
        f"Std deviation   : ₹{ppsf.std():,.0f}"
    )

    # Convert normalized price/sqft into
    # implied value for the target property.
    implied_median = ppsf.median() * target_area
    implied_mean = ppsf.mean() * target_area

    print(
        f"\nTarget value from median ₹/sqft : "
        f"₹{implied_median:,.0f}"
    )

    print(
        f"Target value from mean ₹/sqft   : "
        f"₹{implied_mean:,.0f}"
    )


# ---------------------------------------------------------
# Analyse different geographic scopes
# ---------------------------------------------------------

# 1. All ranked candidates
print_price_statistics(
    candidates.head(20),
    "TOP 20 RANKED COMPARABLES"
)


# 2. Same locality
same_locality = candidates[
    candidates["same_locality"]
]

print_price_statistics(
    same_locality,
    "SAME-LOCALITY COMPARABLES"
)


# 3. Same locality + within 5 km
same_locality_close = candidates[
    candidates["same_locality"]
    & (candidates["distance_km"] <= 5)
]

print_price_statistics(
    same_locality_close,
    "SAME-LOCALITY + WITHIN 5 KM"
)


# 4. Nearby properties regardless of locality
nearby = candidates[
    candidates["distance_km"] <= 5
]

print_price_statistics(
    nearby,
    "ALL COMPARABLES WITHIN 5 KM"
)


# ---------------------------------------------------------
# Display top comparable properties
# ---------------------------------------------------------

display_columns = [
    "property_id",
    "locality",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "asking_price_inr",
    "asking_price_per_sqft",
    "distance_km",
    "same_locality",
    "area_difference_pct",
    "similarity_score",
]


print("\n" + "=" * 80)
print("TOP 20 COMPARABLE PROPERTIES")
print("=" * 80)

print(
    candidates[
        display_columns
    ].head(20).to_string(index=False)
)


# ---------------------------------------------------------
# Save analysis output
# ---------------------------------------------------------

output_columns = display_columns

output_path = (
    OUTPUT_DIR
    / "comparable_price_analysis.csv"
)

candidates[
    output_columns
].to_csv(
    output_path,
    index=False
)


# ---------------------------------------------------------
# Save summary
# ---------------------------------------------------------

summary = {
    "target_property_id": TARGET_PROPERTY_ID,
    "target_city": target_city,
    "target_locality": target_locality,
    "target_area_sqft": float(target_area),
    "target_bedrooms": float(target_bedrooms),
    "target_bathrooms": float(target_bathrooms),
    "candidate_count": int(len(candidates)),
    "same_locality_count": int(
        same_locality.shape[0]
    ),
    "same_locality_within_5km_count": int(
        same_locality_close.shape[0]
    ),
    "within_5km_count": int(
        nearby.shape[0]
    ),
    "top20_median_ppsf": float(
        candidates.head(20)[
            "asking_price_per_sqft"
        ].median()
    ),
    "same_locality_median_ppsf": (
        float(
            same_locality[
                "asking_price_per_sqft"
            ].median()
        )
        if len(same_locality) > 0
        else None
    ),
    "within_5km_median_ppsf": (
        float(
            nearby[
                "asking_price_per_sqft"
            ].median()
        )
        if len(nearby) > 0
        else None
    ),
}


summary_path = (
    OUTPUT_DIR
    / "comparable_price_summary.json"
)


import json

with open(
    summary_path,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        summary,
        f,
        indent=4
    )


print("\n" + "=" * 80)
print("FILES CREATED")
print("=" * 80)

print(output_path)
print(summary_path)

print("\nComparable price analysis completed.")