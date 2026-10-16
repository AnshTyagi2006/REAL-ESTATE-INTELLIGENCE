from pathlib import Path
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASTER_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v1.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "investigation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "duplicate_listing_classification.csv"
)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("DUPLICATE LISTING CLASSIFICATION")
print("=" * 75)

print("\nReading master dataset...")

df = pd.read_csv(
    MASTER_FILE,
    low_memory=False
)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")


# ============================================================
# FIND DUPLICATE LISTING IDs
# ============================================================

listing_counts = df["listing_id"].value_counts()

duplicate_ids = listing_counts[
    listing_counts > 1
].index

duplicate_df = df[
    df["listing_id"].isin(duplicate_ids)
].copy()

print(f"\nDuplicate listing IDs : {len(duplicate_ids):,}")
print(f"Rows involved         : {len(duplicate_df):,}")


# ============================================================
# FIELDS USED FOR COMPARISON
# ============================================================

comparison_fields = [
    "city",
    "locality",
    "configuration",
    "property_type",
    "bedrooms",
    "bathrooms",
    "area_sqft",
    "price_inr",
    "price_per_sqft",
    "latitude",
    "longitude",
]


comparison_fields = [
    field
    for field in comparison_fields
    if field in df.columns
]


# ============================================================
# HELPER FUNCTION
# ============================================================

def values_match(series):
    """
    Returns True if all non-null values in a field
    are the same.

    If all values are missing, returns True.
    """

    values = series.dropna()

    if len(values) == 0:
        return True

    return values.astype(str).nunique() == 1


# ============================================================
# CLASSIFY EACH DUPLICATE LISTING ID
# ============================================================

results = []


for listing_id, group in duplicate_df.groupby(
    "listing_id",
    sort=False
):

    field_results = {}

    for field in comparison_fields:
        field_results[field] = values_match(
            group[field]
        )

    all_fields_match = all(
        field_results.values()
    )

    # --------------------------------------------------------
    # Check whether coordinates match
    # --------------------------------------------------------

    coordinates_match = (
        field_results.get("latitude", True)
        and
        field_results.get("longitude", True)
    )

    # --------------------------------------------------------
    # Check important property information
    # --------------------------------------------------------

    property_details_match = all(
        field_results.get(field, True)
        for field in [
            "city",
            "locality",
            "configuration",
            "property_type",
            "bedrooms",
            "bathrooms",
            "area_sqft",
            "price_inr",
            "price_per_sqft",
        ]
    )

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    if all_fields_match:

        classification = "EXACT_DUPLICATE"

    elif (
        coordinates_match
        and property_details_match
    ):

        classification = "LIKELY_SAME_PROPERTY"

    else:

        classification = "CONFLICTING_RECORD"


    results.append({
        "listing_id": listing_id,
        "rows": len(group),
        "source_cities": " | ".join(
            sorted(
                group["source_city"]
                .dropna()
                .astype(str)
                .unique()
            )
        ),
        "city_values": " | ".join(
            sorted(
                group["city"]
                .dropna()
                .astype(str)
                .unique()
            )
        ),
        "locality_values": " | ".join(
            sorted(
                group["locality"]
                .dropna()
                .astype(str)
                .unique()
            )
        ),
        "coordinates_match": coordinates_match,
        "property_details_match": property_details_match,
        "all_compared_fields_match": all_fields_match,
        "classification": classification,
    })


# ============================================================
# CREATE RESULT DATAFRAME
# ============================================================

result_df = pd.DataFrame(results)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "-" * 75)
print("CLASSIFICATION SUMMARY")
print("-" * 75)

summary = (
    result_df["classification"]
    .value_counts()
)

print(summary.to_string())


# ============================================================
# SAVE RESULT
# ============================================================

result_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print(f"Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("CLASSIFICATION COMPLETE")
print("=" * 75)