from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# 1. PATH
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
print("COMPARABLE PROPERTY ENGINE — SIMILARITY RANKING")
print("=" * 70)


# ============================================================
# 3. TARGET PROPERTY
# ============================================================

target = df.iloc[0].copy()

print("\n" + "-" * 70)
print("TARGET PROPERTY")
print("-" * 70)

print(f"Property ID : {target['property_id']}")
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
# 4. REMOVE TARGET PROPERTY
# ============================================================

candidates = df[
    df["property_id"] != target["property_id"]
].copy()


# ============================================================
# 5. BASIC CANDIDATE RETRIEVAL
# ============================================================

# Same city
candidates = candidates[
    candidates["city"] == target["city"]
].copy()

# Similar area: ±20%
target_area = float(
    target["valuation_area_sqft"]
)

area_lower = target_area * 0.80
area_upper = target_area * 1.20

candidates = candidates[
    candidates[
        "valuation_area_sqft"
    ].between(
        area_lower,
        area_upper
    )
].copy()

# Bedrooms ±1
target_bedrooms = float(
    target["bedrooms"]
)

candidates = candidates[
    (
        candidates["bedrooms"]
        - target_bedrooms
    ).abs() <= 1
].copy()

# Bathrooms ±1
target_bathrooms = float(
    target["bathrooms"]
)

candidates = candidates[
    (
        candidates["bathrooms"]
        - target_bathrooms
    ).abs() <= 1
].copy()


# ============================================================
# 6. GEOGRAPHIC DISTANCE
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


candidates[
    "distance_km"
] = haversine_distance_km(
    target["latitude"],
    target["longitude"],
    candidates["latitude"].values,
    candidates["longitude"].values,
)


# ============================================================
# 7. LOCALITY SIMILARITY
# ============================================================

candidates[
    "locality_similarity"
] = (
    candidates["locality"]
    == target["locality"]
).astype(float)


# ============================================================
# 8. GEOGRAPHIC SIMILARITY
# ============================================================
#
# 0 km      → 1.00
# 5 km      → 0.00
#
# Anything beyond 5 km receives 0.
# ============================================================

distance_scale_km = 5.0

candidates[
    "distance_similarity"
] = (
    1
    - (
        candidates["distance_km"]
        / distance_scale_km
    )
).clip(
    lower=0,
    upper=1
)


# ============================================================
# 9. AREA SIMILARITY
# ============================================================

candidates[
    "area_difference_pct"
] = (
    np.abs(
        candidates[
            "valuation_area_sqft"
        ]
        - target_area
    )
    / target_area
) * 100

# 20% difference = 0 similarity
area_scale_pct = 20.0

candidates[
    "area_similarity"
] = (
    1
    - (
        candidates[
            "area_difference_pct"
        ]
        / area_scale_pct
    )
).clip(
    lower=0,
    upper=1
)


# ============================================================
# 10. BEDROOM SIMILARITY
# ============================================================

candidates[
    "bedroom_difference"
] = np.abs(
    candidates["bedrooms"]
    - target_bedrooms
)

# Difference of 1 = 0 similarity
candidates[
    "bedroom_similarity"
] = (
    1
    - candidates[
        "bedroom_difference"
    ]
).clip(
    lower=0,
    upper=1
)


# ============================================================
# 11. BATHROOM SIMILARITY
# ============================================================

candidates[
    "bathroom_difference"
] = np.abs(
    candidates["bathrooms"]
    - target_bathrooms
)

# Difference of 1 = 0 similarity
candidates[
    "bathroom_similarity"
] = (
    1
    - candidates[
        "bathroom_difference"
    ]
).clip(
    lower=0,
    upper=1
)


# ============================================================
# 12. PROPERTY TYPE SIMILARITY
# ============================================================
#
# If both target and candidate have property types:
#
# Same type     → 1
# Different     → 0
#
# If either is missing:
# property type does not contribute to the score.
# ============================================================

target_property_type = target[
    "property_type"
]

if pd.notna(target_property_type):

    candidates[
        "property_type_available"
    ] = candidates[
        "property_type"
    ].notna()

    candidates[
        "property_type_similarity"
    ] = np.where(
        candidates[
            "property_type_available"
        ],
        (
            candidates[
                "property_type"
            ]
            == target_property_type
        ).astype(float),
        np.nan,
    )

else:

    candidates[
        "property_type_available"
    ] = False

    candidates[
        "property_type_similarity"
    ] = np.nan


# ============================================================
# 13. WEIGHTS
# ============================================================

weights = {
    "locality_similarity": 0.30,
    "distance_similarity": 0.20,
    "area_similarity": 0.20,
    "bedroom_similarity": 0.10,
    "bathroom_similarity": 0.10,
    "property_type_similarity": 0.10,
}


# ============================================================
# 14. CALCULATE WEIGHTED SCORE
# ============================================================
#
# If property type is unavailable, its weight is removed
# and the remaining components are normalized.
# ============================================================

score_columns = []

for feature, weight in weights.items():

    available = (
        candidates[feature].notna()
    )

    candidates[
        f"{feature}_weighted"
    ] = (
        candidates[feature]
        .fillna(0)
        * weight
    )

    candidates[
        f"{feature}_weight_available"
    ] = (
        available.astype(float)
        * weight
    )

    score_columns.append(
        f"{feature}_weighted"
    )


candidates["raw_similarity_score"] = (
    candidates[score_columns]
    .sum(axis=1)
)

available_weight_columns = [
    f"{feature}_weight_available"
    for feature in weights
]

candidates["available_weight"] = (
    candidates[
        available_weight_columns
    ]
    .sum(axis=1)
)


# Avoid division by zero
candidates["similarity_score"] = np.where(
    candidates["available_weight"] > 0,
    (
        candidates["raw_similarity_score"]
        / candidates["available_weight"]
    ) * 100,
    0,
)


# ============================================================
# 15. RANK CANDIDATES
# ============================================================

candidates = candidates.sort_values(
    by=[
        "similarity_score",
        "distance_km",
        "area_difference_pct",
    ],
    ascending=[
        False,
        True,
        True,
    ],
).reset_index(drop=True)


candidates[
    "similarity_rank"
] = np.arange(
    1,
    len(candidates) + 1
)


# ============================================================
# 16. DISPLAY TOP 10
# ============================================================

display_columns = [
    "similarity_rank",
    "property_id",
    "locality",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "asking_price_inr",
    "distance_km",
    "same_locality",
    "area_difference_pct",
    "similarity_score",
]

# Create same_locality for display
candidates[
    "same_locality"
] = candidates[
    "locality"
] == target["locality"]


print("\n" + "-" * 70)
print("TOP 10 RANKED COMPARABLE CANDIDATES")
print("-" * 70)

print(
    candidates[
        display_columns
    ]
    .head(10)
    .to_string(index=False)
)


# ============================================================
# 17. SCORE COMPONENTS FOR TOP 10
# ============================================================

component_columns = [
    "similarity_rank",
    "property_id",
    "locality_similarity",
    "distance_similarity",
    "area_similarity",
    "bedroom_similarity",
    "bathroom_similarity",
    "property_type_similarity",
    "similarity_score",
]

print("\n" + "-" * 70)
print("SIMILARITY SCORE BREAKDOWN — TOP 10")
print("-" * 70)

print(
    candidates[
        component_columns
    ]
    .head(10)
    .to_string(index=False)
)


# ============================================================
# 18. SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("RANKING SUMMARY")
print("=" * 70)

print(
    f"\nCandidate pool: "
    f"{len(candidates):,}"
)

print(
    "\nTop 10 candidates selected "
    "for inspection."
)

print(
    "\nSimilarity ranking completed."
)
