from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "modeling"
    / "valuation_modeling_dataset.csv"
)


# ============================================================
# 2. LOAD DATA
# ============================================================

df = pd.read_csv(DATA_PATH)

print("=" * 70)
print("COMPARABLE PROPERTY ENGINE — CANDIDATE RETRIEVAL")
print("=" * 70)

print(
    f"\nTotal properties in dataset: {len(df):,}"
)


# ============================================================
# 3. TARGET PROPERTY
# ============================================================
#
# For this first test we use one real property from the
# dataset as our target.
#
# Later the frontend/API will provide these values dynamically.
# ============================================================

target = df.iloc[0].copy()

print("\n" + "-" * 70)
print("TARGET PROPERTY")
print("-" * 70)

print(f"Property ID : {target['property_id']}")
print(f"Listing ID  : {target['listing_id']}")
print(f"City        : {target['city']}")
print(f"Locality    : {target['locality']}")
print(
    f"Area        : "
    f"{target['valuation_area_sqft']:,.0f} sqft"
)
print(f"Bedrooms    : {target['bedrooms']}")
print(f"Bathrooms   : {target['bathrooms']}")

if pd.notna(target["property_type"]):
    print(
        f"Property Type: "
        f"{target['property_type']}"
    )
else:
    print("Property Type: Not available")


# ============================================================
# 4. REMOVE THE TARGET PROPERTY
# ============================================================
#
# A property must NEVER become its own comparable.
# ============================================================

candidates = df[
    df["property_id"] != target["property_id"]
].copy()


# ============================================================
# 5. BASIC VALIDATION
# ============================================================

required_target_fields = [
    "city",
    "locality",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
]

missing_target_fields = [
    field
    for field in required_target_fields
    if pd.isna(target[field])
]

if missing_target_fields:
    raise ValueError(
        "Target property is missing required fields: "
        f"{missing_target_fields}"
    )


# ============================================================
# 6. SAME-CITY FILTER
# ============================================================

same_city = candidates[
    candidates["city"] == target["city"]
].copy()

print("\n" + "-" * 70)
print("CANDIDATE RETRIEVAL")
print("-" * 70)

print(
    f"Same-city candidates: "
    f"{len(same_city):,}"
)


# ============================================================
# 7. AREA FILTER
# ============================================================
#
# Keep properties within ±20% of target area.
#
# Example:
# Target = 1500 sqft
#
# Lower = 1200 sqft
# Upper = 1800 sqft
# ============================================================

target_area = float(
    target["valuation_area_sqft"]
)

area_lower = target_area * 0.80
area_upper = target_area * 1.20

same_city_area = same_city[
    same_city["valuation_area_sqft"].between(
        area_lower,
        area_upper,
        inclusive="both",
    )
].copy()

print(
    f"Same city + similar area: "
    f"{len(same_city_area):,}"
)

print(
    f"Area range: "
    f"{area_lower:,.0f} – "
    f"{area_upper:,.0f} sqft"
)


# ============================================================
# 8. BEDROOM FILTER
# ============================================================
#
# Allow a difference of at most 1 bedroom.
#
# Example:
# Target = 3 BHK
# Allowed = 2, 3, 4 BHK
# ============================================================

target_bedrooms = float(
    target["bedrooms"]
)

same_city_area_bedrooms = (
    same_city_area[
        (
            same_city_area["bedrooms"]
            - target_bedrooms
        ).abs() <= 1
    ]
    .copy()
)

print(
    f"Same city + area + bedroom range: "
    f"{len(same_city_area_bedrooms):,}"
)


# ============================================================
# 9. BATHROOM FILTER
# ============================================================
#
# Allow a difference of at most 1 bathroom.
# ============================================================

target_bathrooms = float(
    target["bathrooms"]
)

candidate_pool = (
    same_city_area_bedrooms[
        (
            same_city_area_bedrooms["bathrooms"]
            - target_bathrooms
        ).abs() <= 1
    ]
    .copy()
)

print(
    f"Same city + area + bedroom + "
    f"bathroom range: "
    f"{len(candidate_pool):,}"
)


# ============================================================
# 10. CALCULATE GEOGRAPHIC DISTANCE
# ============================================================
#
# Latitude and longitude allow us to estimate the distance
# between the target and every candidate.
#
# Haversine formula calculates approximate distance
# between two points on Earth.
# ============================================================

def haversine_distance_km(
    lat1,
    lon1,
    lat2,
    lon2,
):
    earth_radius_km = 6371.0

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(delta_lon / 2) ** 2
    )

    c = 2 * np.arcsin(
        np.sqrt(a)
    )

    return earth_radius_km * c


candidate_pool[
    "distance_km"
] = haversine_distance_km(
    target["latitude"],
    target["longitude"],
    candidate_pool["latitude"].values,
    candidate_pool["longitude"].values,
)


# ============================================================
# 11. SAME LOCALITY FLAG
# ============================================================

candidate_pool[
    "same_locality"
] = (
    candidate_pool["locality"]
    == target["locality"]
)


# ============================================================
# 12. AREA DIFFERENCE
# ============================================================

candidate_pool[
    "area_difference_pct"
] = (
    np.abs(
        candidate_pool[
            "valuation_area_sqft"
        ]
        - target_area
    )
    / target_area
) * 100


# ============================================================
# 13. BEDROOM DIFFERENCE
# ============================================================

candidate_pool[
    "bedroom_difference"
] = np.abs(
    candidate_pool["bedrooms"]
    - target_bedrooms
)


# ============================================================
# 14. BATHROOM DIFFERENCE
# ============================================================

candidate_pool[
    "bathroom_difference"
] = np.abs(
    candidate_pool["bathrooms"]
    - target_bathrooms
)


# ============================================================
# 15. SORT CANDIDATES
# ============================================================
#
# At this stage we are NOT creating a final similarity score.
#
# We simply put stronger candidates first using:
#
# 1. Same locality
# 2. Geographic distance
# 3. Area difference
# ============================================================

candidate_pool = candidate_pool.sort_values(
    by=[
        "same_locality",
        "distance_km",
        "area_difference_pct",
    ],
    ascending=[
        False,
        True,
        True,
    ],
)


# ============================================================
# 16. DISPLAY TOP CANDIDATES
# ============================================================

display_columns = [
    "property_id",
    "city",
    "locality",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "asking_price_inr",
    "distance_km",
    "same_locality",
    "area_difference_pct",
    "bedroom_difference",
    "bathroom_difference",
]

print("\n" + "-" * 70)
print("TOP 20 CANDIDATE PROPERTIES")
print("-" * 70)

if len(candidate_pool) == 0:

    print(
        "No candidates found using the current rules."
    )

else:

    print(
        candidate_pool[
            display_columns
        ]
        .head(20)
        .to_string(index=False)
    )


# ============================================================
# 17. CANDIDATE SUMMARY
# ============================================================

same_locality_count = (
    candidate_pool[
        "same_locality"
    ].sum()
)

print("\n" + "-" * 70)
print("CANDIDATE SUMMARY")
print("-" * 70)

print(
    f"Final candidate pool: "
    f"{len(candidate_pool):,}"
)

print(
    f"Same-locality candidates: "
    f"{same_locality_count:,}"
)

if len(candidate_pool) > 0:

    print(
        f"Closest candidate: "
        f"{candidate_pool['distance_km'].min():.2f} km"
    )

    print(
        f"Farthest candidate: "
        f"{candidate_pool['distance_km'].max():.2f} km"
    )

print(
    "\nCandidate retrieval completed."
)