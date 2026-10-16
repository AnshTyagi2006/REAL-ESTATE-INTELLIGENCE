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


# Number of comparables we want
TARGET_COMPARABLE_COUNT = 8


# Geographic thresholds
LOCALITY_DISTANCE_KM = 5.0
TIER_3_DISTANCE_KM = 15.0


# =========================================================
# LOAD DATA
# =========================================================

df = pd.read_csv(INPUT_PATH)

target_rows = df[
    df["property_id"] == TARGET_PROPERTY_ID
]

if target_rows.empty:
    raise ValueError(
        f"Target property {TARGET_PROPERTY_ID} not found."
    )

target = target_rows.iloc[0]


# =========================================================
# TARGET INFORMATION
# =========================================================

target_city = target["city"]
target_locality = target["locality"]
target_area = target["valuation_area_sqft"]
target_bedrooms = target["bedrooms"]
target_bathrooms = target["bathrooms"]
target_property_type = target["property_type"]


print("=" * 90)
print("COMPARABLE PROPERTY VALUATION ENGINE")
print("=" * 90)

print(f"\nTarget Property : {TARGET_PROPERTY_ID}")
print(f"City            : {target_city}")
print(f"Locality        : {target_locality}")
print(f"Area            : {target_area:,.2f} sqft")
print(f"Bedrooms        : {target_bedrooms}")
print(f"Bathrooms       : {target_bathrooms}")
print(f"Property Type   : {target_property_type}")


# =========================================================
# HAVERSINE DISTANCE
# =========================================================

EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1, lon1, lat2, lon2):

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


# =========================================================
# CREATE INITIAL CANDIDATE POOL
# =========================================================

candidates = df[
    (df["property_id"] != TARGET_PROPERTY_ID)
    & (df["city"] == target_city)
].copy()


print(
    f"\nSame-city properties: {len(candidates)}"
)


# ---------------------------------------------------------
# Area similarity
# ---------------------------------------------------------

area_min = target_area * 0.80
area_max = target_area * 1.20

candidates = candidates[
    candidates["valuation_area_sqft"].between(
        area_min,
        area_max
    )
].copy()


# ---------------------------------------------------------
# Bedroom similarity
# ---------------------------------------------------------

candidates = candidates[
    candidates["bedrooms"].between(
        target_bedrooms - 1,
        target_bedrooms + 1
    )
].copy()


# ---------------------------------------------------------
# Bathroom similarity
# ---------------------------------------------------------

candidates = candidates[
    candidates["bathrooms"].between(
        target_bathrooms - 1,
        target_bathrooms + 1
    )
].copy()


print(
    f"After core property filters: {len(candidates)}"
)


# =========================================================
# DISTANCE
# =========================================================

candidates["distance_km"] = haversine_distance(
    target["latitude"],
    target["longitude"],
    candidates["latitude"],
    candidates["longitude"]
)


# =========================================================
# COMPARABLE ATTRIBUTES
# =========================================================

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


candidates["asking_price_per_sqft"] = (
    candidates["asking_price_inr"]
    / candidates["valuation_area_sqft"]
)


# =========================================================
# GEOGRAPHIC TIERS
# =========================================================

def assign_tier(row):

    if (
        row["same_locality"]
        and row["distance_km"] <= LOCALITY_DISTANCE_KM
    ):
        return 1

    if row["distance_km"] <= LOCALITY_DISTANCE_KM:
        return 2

    if row["distance_km"] <= TIER_3_DISTANCE_KM:
        return 3

    return 4


candidates["geographic_tier"] = (
    candidates.apply(
        assign_tier,
        axis=1
    )
)


# =========================================================
# SIMILARITY SCORES
# =========================================================

# Locality
candidates["locality_score"] = np.where(
    candidates["same_locality"],
    1.0,
    0.0
)


# Distance
candidates["distance_score"] = (
    1
    - candidates["distance_km"] / 5
).clip(0, 1)


# Area
candidates["area_score"] = (
    1
    - candidates["area_difference_pct"] / 20
).clip(0, 1)


# Bedrooms
candidates["bedroom_score"] = (
    1
    - candidates["bedroom_difference"]
).clip(0, 1)


# Bathrooms
candidates["bathroom_score"] = (
    1
    - candidates["bathroom_difference"]
).clip(0, 1)


# Property type
property_type_known = (
    pd.notna(target_property_type)
    & candidates["property_type"].notna()
)


candidates["property_type_score"] = np.where(
    property_type_known,
    (
        candidates["property_type"]
        == target_property_type
    ).astype(float),
    np.nan
)


# =========================================================
# BASE SIMILARITY SCORE
# =========================================================

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


# =========================================================
# GEOGRAPHIC TIER ADJUSTMENT
# =========================================================

# Geographic tier controls the maximum influence
# a comparable can have.

tier_multiplier = {
    1: 1.00,
    2: 0.75,
    3: 0.50,
    4: 0.00,
}


candidates["tier_multiplier"] = (
    candidates["geographic_tier"]
    .map(tier_multiplier)
)


candidates["final_weight"] = (
    candidates["similarity_score"]
    * candidates["tier_multiplier"]
)


# =========================================================
# REMOVE TIER 4
# =========================================================

usable = candidates[
    candidates["geographic_tier"] <= 3
].copy()


print("\n" + "-" * 90)
print("GEOGRAPHIC TIER DISTRIBUTION")
print("-" * 90)

tier_counts = (
    candidates["geographic_tier"]
    .value_counts()
    .sort_index()
)


for tier, count in tier_counts.items():

    if tier == 1:
        description = (
            "Same locality + within 5 km"
        )

    elif tier == 2:
        description = (
            "Different locality + within 5 km"
        )

    elif tier == 3:
        description = (
            "5–15 km fallback"
        )

    else:
        description = (
            ">15 km excluded"
        )

    print(
        f"Tier {tier}: {count} properties "
        f"— {description}"
    )


# =========================================================
# SELECT COMPARABLES
# =========================================================

# Sort primarily by geographic tier,
# then by similarity.

usable = usable.sort_values(
    by=[
        "geographic_tier",
        "final_weight",
        "distance_km",
        "area_difference_pct",
    ],
    ascending=[
        True,
        False,
        True,
        True,
    ]
).copy()


# Prefer Tier 1.
tier_1 = usable[
    usable["geographic_tier"] == 1
]

tier_2 = usable[
    usable["geographic_tier"] == 2
]

tier_3 = usable[
    usable["geographic_tier"] == 3
]


selected_parts = []


# First take strongest Tier 1 properties.
if len(tier_1) > 0:

    selected_parts.append(
        tier_1.head(TARGET_COMPARABLE_COUNT)
    )


selected = pd.concat(
    selected_parts,
    ignore_index=True
) if selected_parts else pd.DataFrame()


# If we don't have enough strong local comparables,
# use Tier 2.

if len(selected) < TARGET_COMPARABLE_COUNT:

    remaining = (
        TARGET_COMPARABLE_COUNT
        - len(selected)
    )

    tier_2_remaining = tier_2[
        ~tier_2["property_id"].isin(
            selected["property_id"]
        )
    ]

    selected = pd.concat(
        [
            selected,
            tier_2_remaining.head(remaining),
        ],
        ignore_index=True
    )


# If still insufficient, use Tier 3.

if len(selected) < TARGET_COMPARABLE_COUNT:

    remaining = (
        TARGET_COMPARABLE_COUNT
        - len(selected)
    )

    tier_3_remaining = tier_3[
        ~tier_3["property_id"].isin(
            selected["property_id"]
        )
    ]

    selected = pd.concat(
        [
            selected,
            tier_3_remaining.head(remaining),
        ],
        ignore_index=True
    )


# =========================================================
# OUTLIER FILTERING
# =========================================================

# Use the selected comparable pool to identify
# extreme asking-price-per-sqft values.

q1 = selected[
    "asking_price_per_sqft"
].quantile(0.25)

q3 = selected[
    "asking_price_per_sqft"
].quantile(0.75)

iqr = q3 - q1

lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr


selected["price_outlier"] = (
    (selected["asking_price_per_sqft"] < lower_bound)
    |
    (selected["asking_price_per_sqft"] > upper_bound)
)


selected_for_valuation = selected[
    ~selected["price_outlier"]
].copy()


# =========================================================
# WEIGHTED MEDIAN
# =========================================================

def weighted_median(values, weights):

    values = np.asarray(values)
    weights = np.asarray(weights)

    order = np.argsort(values)

    values = values[order]
    weights = weights[order]

    cumulative_weights = np.cumsum(weights)

    cutoff = weights.sum() / 2

    return values[
        cumulative_weights >= cutoff
    ][0]


weighted_ppsf = weighted_median(
    selected_for_valuation[
        "asking_price_per_sqft"
    ].values,
    selected_for_valuation[
        "final_weight"
    ].values
)


# =========================================================
# UNWEIGHTED STATISTICS
# =========================================================

ppsf = selected_for_valuation[
    "asking_price_per_sqft"
]


median_ppsf = ppsf.median()
mean_ppsf = ppsf.mean()

p25_ppsf = ppsf.quantile(0.25)
p75_ppsf = ppsf.quantile(0.75)


# =========================================================
# IMPLIED PROPERTY VALUES
# =========================================================

median_value = (
    median_ppsf
    * target_area
)

weighted_value = (
    weighted_ppsf
    * target_area
)

mean_value = (
    mean_ppsf
    * target_area
)

p25_value = (
    p25_ppsf
    * target_area
)

p75_value = (
    p75_ppsf
    * target_area
)


# =========================================================
# EVIDENCE QUALITY
# =========================================================

tier_1_selected = selected[
    selected["geographic_tier"] == 1
]

same_locality_selected_count = len(
    tier_1_selected
)

total_selected_count = len(
    selected_for_valuation
)


if same_locality_selected_count >= 5:
    evidence_level = "STRONG"

elif same_locality_selected_count >= 3:
    evidence_level = "MODERATE"

elif total_selected_count >= 5:
    evidence_level = "LIMITED"

else:
    evidence_level = "WEAK"


# =========================================================
# OUTPUT
# =========================================================

print("\n" + "=" * 90)
print("SELECTED COMPARABLES")
print("=" * 90)

display_columns = [
    "property_id",
    "locality",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "asking_price_inr",
    "asking_price_per_sqft",
    "distance_km",
    "geographic_tier",
    "similarity_score",
    "final_weight",
    "price_outlier",
]


print(
    selected[
        display_columns
    ].to_string(index=False)
)


print("\n" + "=" * 90)
print("COMPARABLE PRICE EVIDENCE")
print("=" * 90)

print(
    f"Selected comparables        : "
    f"{len(selected)}"
)

print(
    f"Used for valuation          : "
    f"{len(selected_for_valuation)}"
)

print(
    f"Price outliers removed      : "
    f"{selected['price_outlier'].sum()}"
)

print(
    f"Same-locality comparables   : "
    f"{same_locality_selected_count}"
)

print(
    f"\n25th percentile ₹/sqft     : "
    f"₹{p25_ppsf:,.0f}"
)

print(
    f"Median ₹/sqft               : "
    f"₹{median_ppsf:,.0f}"
)

print(
    f"Weighted median ₹/sqft     : "
    f"₹{weighted_ppsf:,.0f}"
)

print(
    f"Mean ₹/sqft                : "
    f"₹{mean_ppsf:,.0f}"
)

print(
    f"75th percentile ₹/sqft     : "
    f"₹{p75_ppsf:,.0f}"
)


print("\n" + "=" * 90)
print("COMPARABLE-BASED VALUE SIGNAL")
print("=" * 90)

print(
    f"25th percentile value      : "
    f"₹{p25_value:,.0f}"
)

print(
    f"Median-based value         : "
    f"₹{median_value:,.0f}"
)

print(
    f"Weighted median value      : "
    f"₹{weighted_value:,.0f}"
)

print(
    f"Mean-based value           : "
    f"₹{mean_value:,.0f}"
)

print(
    f"75th percentile value      : "
    f"₹{p75_value:,.0f}"
)


print("\n" + "=" * 90)
print("EVIDENCE QUALITY")
print("=" * 90)

print(
    f"Evidence level : {evidence_level}"
)

print(
    "\nNote: This is an asking-price-based "
    "comparative value signal, not a verified "
    "transaction price."
)


# =========================================================
# SAVE SELECTED COMPARABLES
# =========================================================

selected_path = (
    OUTPUT_DIR
    / "selected_comparables.csv"
)

selected[
    display_columns
].to_csv(
    selected_path,
    index=False
)


# =========================================================
# SAVE VALUATION SUMMARY
# =========================================================

summary = {

    "target_property_id":
        TARGET_PROPERTY_ID,

    "target_city":
        target_city,

    "target_locality":
        target_locality,

    "target_area_sqft":
        float(target_area),

    "selected_comparable_count":
        int(len(selected)),

    "valuation_comparable_count":
        int(len(selected_for_valuation)),

    "same_locality_comparable_count":
        int(same_locality_selected_count),

    "price_outliers_removed":
        int(
            selected["price_outlier"].sum()
        ),

    "p25_ppsf":
        float(p25_ppsf),

    "median_ppsf":
        float(median_ppsf),

    "weighted_median_ppsf":
        float(weighted_ppsf),

    "mean_ppsf":
        float(mean_ppsf),

    "p75_ppsf":
        float(p75_ppsf),

    "p25_value":
        float(p25_value),

    "median_value":
        float(median_value),

    "weighted_median_value":
        float(weighted_value),

    "mean_value":
        float(mean_value),

    "p75_value":
        float(p75_value),

    "evidence_level":
        evidence_level,
}


summary_path = (
    OUTPUT_DIR
    / "comparable_valuation_summary.json"
)


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


print("\n" + "=" * 90)
print("FILES CREATED")
print("=" * 90)

print(selected_path)
print(summary_path)

print("\nComparable valuation completed.")