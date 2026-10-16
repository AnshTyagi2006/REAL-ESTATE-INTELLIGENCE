from pathlib import Path
import json
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v4.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "investigation"

JSON_OUTPUT = (
    OUTPUT_DIR
    / "valuation_eligibility_report.json"
)

CITY_OUTPUT = (
    OUTPUT_DIR
    / "valuation_eligibility_by_city.csv"
)


# ============================================================
# HELPERS
# ============================================================

def count_valid(df, columns):
    """
    Count rows where every requested column is non-null.
    """
    return int(df[columns].notna().all(axis=1).sum())


def pct(count, total):
    if total == 0:
        return 0.0
    return round(count / total * 100, 2)


# ============================================================
# HEADER
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("VALUATION ELIGIBILITY ANALYSIS")
print("=" * 75)


# ============================================================
# LOAD MASTER V4
# ============================================================

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(f"Input file : {INPUT_FILE}")
print(f"Rows       : {len(df):,}")
print(f"Columns    : {len(df.columns):,}")


# ============================================================
# REQUIRED FIELD CHECK
# ============================================================

required_columns = [
    "asking_price_inr",
    "valuation_area_sqft",
    "city",
    "locality",
]

missing_columns = [
    col
    for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Required columns missing: {missing_columns}"
    )


# ============================================================
# BASIC VALIDITY MASKS
# ============================================================

price_available = (
    df["asking_price_inr"].notna()
    & (df["asking_price_inr"] > 0)
)

area_available = (
    df["valuation_area_sqft"].notna()
    & (df["valuation_area_sqft"] > 0)
)

city_available = (
    df["city"].notna()
    & df["city"].astype(str).str.strip().ne("")
)

locality_available = (
    df["locality"].notna()
    & df["locality"].astype(str).str.strip().ne("")
)


# ============================================================
# 1. FOUR MAIN ELIGIBILITY GROUPS
# ============================================================

print("\n" + "-" * 75)
print("PRIMARY ELIGIBILITY GROUPS")
print("-" * 75)

price_only = (
    price_available
    & ~area_available
)

area_only = (
    area_available
    & ~price_available
)

price_and_area = (
    price_available
    & area_available
)

neither = (
    ~price_available
    & ~area_available
)

groups = {
    "PRICE_ONLY": int(price_only.sum()),
    "AREA_ONLY": int(area_only.sum()),
    "PRICE_AND_AREA": int(price_and_area.sum()),
    "NEITHER": int(neither.sum()),
}

for name, count in groups.items():
    print(
        f"{name:<18} "
        f"{count:>6,} "
        f"({pct(count, len(df)):>6.2f}%)"
    )


# ============================================================
# 2. PRICE + AREA + ADDITIONAL FEATURES
# ============================================================

print("\n" + "-" * 75)
print("PROGRESSIVE VALUATION ELIGIBILITY")
print("-" * 75)

feature_sets = {
    "PRICE_AND_AREA": [
        "asking_price_inr",
        "valuation_area_sqft",
    ],

    "PRICE_AREA_CITY": [
        "asking_price_inr",
        "valuation_area_sqft",
        "city",
    ],

    "PRICE_AREA_BEDROOMS": [
        "asking_price_inr",
        "valuation_area_sqft",
        "bedrooms",
    ],

    "PRICE_AREA_BATHROOMS": [
        "asking_price_inr",
        "valuation_area_sqft",
        "bathrooms",
    ],

    "PRICE_AREA_LOCALITY": [
        "asking_price_inr",
        "valuation_area_sqft",
        "locality",
    ],

    "PRICE_AREA_LAT_LON": [
        "asking_price_inr",
        "valuation_area_sqft",
        "latitude",
        "longitude",
    ],

    "PRICE_AREA_BEDROOMS_BATHROOMS_LOCALITY": [
        "asking_price_inr",
        "valuation_area_sqft",
        "bedrooms",
        "bathrooms",
        "locality",
    ],

    "PRICE_AREA_CORE_FEATURES": [
        "asking_price_inr",
        "valuation_area_sqft",
        "city",
        "locality",
        "bedrooms",
        "bathrooms",
    ],
}

progressive_results = {}

for name, columns in feature_sets.items():

    missing = [
        col for col in columns
        if col not in df.columns
    ]

    if missing:
        progressive_results[name] = {
            "count": 0,
            "percentage": 0.0,
            "missing_columns": missing,
        }

        print(
            f"{name:<42} "
            f"UNAVAILABLE - missing {missing}"
        )

        continue

    count = count_valid(df, columns)

    progressive_results[name] = {
        "count": count,
        "percentage": pct(count, len(df)),
        "missing_columns": [],
    }

    print(
        f"{name:<42} "
        f"{count:>6,} "
        f"({pct(count, len(df)):>6.2f}%)"
    )


# ============================================================
# 3. CORE FEATURE AVAILABILITY
# ============================================================

print("\n" + "-" * 75)
print("CORE FEATURE AVAILABILITY")
print("-" * 75)

core_features = [
    "asking_price_inr",
    "valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "property_type",
    "furnishing",
    "floor",
    "total_floors",
    "seller_type",
    "parking",
    "facing",
]

feature_availability = {}

for col in core_features:

    if col not in df.columns:
        continue

    count = int(df[col].notna().sum())

    feature_availability[col] = {
        "count": count,
        "percentage": pct(count, len(df)),
    }

    print(
        f"{col:<25} "
        f"{count:>6,} "
        f"({pct(count, len(df)):>6.2f}%)"
    )


# ============================================================
# 4. FEATURES WITHIN PRICE + AREA POPULATION
# ============================================================

print("\n" + "-" * 75)
print("FEATURE AVAILABILITY WITHIN PRICE + AREA DATA")
print("-" * 75)

pa_df = df.loc[price_and_area].copy()

print(
    f"Price + area population : "
    f"{len(pa_df):,}"
)

feature_availability_pa = {}

for col in core_features:

    if col not in pa_df.columns:
        continue

    count = int(pa_df[col].notna().sum())

    feature_availability_pa[col] = {
        "count": count,
        "percentage": pct(count, len(pa_df)),
    }

    print(
        f"{col:<25} "
        f"{count:>6,} "
        f"({pct(count, len(pa_df)):>6.2f}%)"
    )


# ============================================================
# 5. PRICE + AREA BY SOURCE CITY
# ============================================================

print("\n" + "-" * 75)
print("PRICE + AREA ELIGIBILITY BY SOURCE CITY")
print("-" * 75)

city_rows = []

for source_city, group in df.groupby(
    "source_city",
    dropna=False
):

    total = len(group)

    price_count = int(
        price_available.loc[group.index].sum()
    )

    area_count = int(
        area_available.loc[group.index].sum()
    )

    both_count = int(
        price_and_area.loc[group.index].sum()
    )

    city_rows.append({
        "source_city": source_city,
        "total_rows": total,
        "price_available": price_count,
        "price_pct": pct(price_count, total),
        "area_available": area_count,
        "area_pct": pct(area_count, total),
        "price_and_area": both_count,
        "price_and_area_pct": pct(both_count, total),
    })


city_summary = pd.DataFrame(city_rows)

city_summary = city_summary.sort_values(
    "total_rows",
    ascending=False
)

print(
    city_summary.to_string(index=False)
)


# ============================================================
# 6. PRICE + AREA BY ACTUAL CITY
# ============================================================

print("\n" + "-" * 75)
print("PRICE + AREA ELIGIBILITY BY PROPERTY CITY")
print("-" * 75)

property_city_rows = []

for city, group in df.groupby(
    "city",
    dropna=False
):

    total = len(group)

    price_count = int(
        price_available.loc[group.index].sum()
    )

    area_count = int(
        area_available.loc[group.index].sum()
    )

    both_count = int(
        price_and_area.loc[group.index].sum()
    )

    property_city_rows.append({
        "city": city,
        "total_rows": total,
        "price_available": price_count,
        "price_pct": pct(price_count, total),
        "area_available": area_count,
        "area_pct": pct(area_count, total),
        "price_and_area": both_count,
        "price_and_area_pct": pct(both_count, total),
    })


property_city_summary = pd.DataFrame(
    property_city_rows
)

property_city_summary = property_city_summary.sort_values(
    "total_rows",
    ascending=False
)

print(
    property_city_summary.to_string(
        index=False
    )
)


# ============================================================
# 7. PRICE + AREA RECORDS WITH HIGH FEATURE COMPLETENESS
# ============================================================

print("\n" + "-" * 75)
print("FEATURE COMPLETENESS WITHIN PRICE + AREA DATA")
print("-" * 75)

candidate_features = [
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "property_type",
    "furnishing",
    "floor",
    "total_floors",
    "seller_type",
    "parking",
    "facing",
]

candidate_features = [
    col
    for col in candidate_features
    if col in pa_df.columns
]

if len(pa_df) > 0:

    completeness = (
        pa_df[candidate_features]
        .notna()
        .sum(axis=1)
    )

    print(
        "Feature completeness among "
        f"{len(candidate_features)} candidate features:"
    )

    print(
        f"  100% complete : "
        f"{int((completeness == len(candidate_features)).sum()):,}"
    )

    print(
        f"  >= 90%       : "
        f"{int((completeness >= len(candidate_features) * 0.90).sum()):,}"
    )

    print(
        f"  >= 75%       : "
        f"{int((completeness >= len(candidate_features) * 0.75).sum()):,}"
    )

    print(
        f"  >= 50%       : "
        f"{int((completeness >= len(candidate_features) * 0.50).sum()):,}"
    )


# ============================================================
# 8. MODEL-READY MINIMUM SET
# ============================================================

print("\n" + "-" * 75)
print("MODEL-READY MINIMUM SET")
print("-" * 75)

minimum_model_features = [
    "asking_price_inr",
    "valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
]

minimum_model_mask = (
    df[minimum_model_features]
    .notna()
    .all(axis=1)
)

minimum_model_count = int(
    minimum_model_mask.sum()
)

print(
    f"Required fields:"
)

for col in minimum_model_features:
    print(f"  - {col}")

print(
    f"\nComplete records : "
    f"{minimum_model_count:,} "
    f"({pct(minimum_model_count, len(df)):.2f}%)"
)


# ============================================================
# 9. GEO-ENABLED MODEL SET
# ============================================================

geo_model_features = [
    "asking_price_inr",
    "valuation_area_sqft",
    "city",
    "locality",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
]

geo_model_mask = (
    df[geo_model_features]
    .notna()
    .all(axis=1)
)

geo_model_count = int(
    geo_model_mask.sum()
)

print(
    f"\nGeo-enabled complete records : "
    f"{geo_model_count:,} "
    f"({pct(geo_model_count, len(df)):.2f}%)"
)


# ============================================================
# 10. SAVE CITY REPORT
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

city_summary.to_csv(
    CITY_OUTPUT,
    index=False
)


# ============================================================
# 11. SAVE JSON REPORT
# ============================================================

report = {
    "dataset": {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
    },

    "primary_groups": groups,

    "progressive_eligibility": progressive_results,

    "feature_availability_all_records":
        feature_availability,

    "feature_availability_price_area":
        feature_availability_pa,

    "minimum_model_features": {
        "features": minimum_model_features,
        "complete_records": minimum_model_count,
        "percentage": pct(
            minimum_model_count,
            len(df)
        ),
    },

    "geo_model_features": {
        "features": geo_model_features,
        "complete_records": geo_model_count,
        "percentage": pct(
            geo_model_count,
            len(df)
        ),
    },

    "source_city_summary":
        city_summary.to_dict(
            orient="records"
        ),

    "property_city_summary":
        property_city_summary.to_dict(
            orient="records"
        ),
}


with open(
    JSON_OUTPUT,
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

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print(
    f"JSON report:\n{JSON_OUTPUT}"
)

print(
    f"\nCity report:\n{CITY_OUTPUT}"
)

print("\n" + "=" * 75)
print("VALUATION ELIGIBILITY ANALYSIS COMPLETE")
print("=" * 75)

print("\nMaster V4 was NOT modified.")