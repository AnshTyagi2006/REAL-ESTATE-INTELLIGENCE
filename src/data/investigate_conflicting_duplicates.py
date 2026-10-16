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
    / "conflicting_duplicate_details.csv"
)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("CONFLICTING DUPLICATE INVESTIGATION")
print("=" * 75)

df = pd.read_csv(
    MASTER_FILE,
    low_memory=False
)

print("\nReading master dataset...")
print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")


# ============================================================
# FIND DUPLICATE LISTING IDS
# ============================================================

listing_counts = df["listing_id"].value_counts()

duplicate_ids = listing_counts[
    listing_counts > 1
].index

duplicate_df = df[
    df["listing_id"].isin(duplicate_ids)
].copy()


# ============================================================
# FIELDS TO COMPARE
# ============================================================

comparison_fields = [
    "source_city",
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
# FIND CONFLICTING LISTING IDS
# ============================================================

conflicting_ids = []

for listing_id, group in duplicate_df.groupby(
    "listing_id",
    sort=False
):

    has_conflict = False

    for field in comparison_fields:

        values = group[field].dropna()

        if len(values) > 0 and values.astype(str).nunique() > 1:
            has_conflict = True
            break

    if has_conflict:
        conflicting_ids.append(listing_id)


print("\n" + "-" * 75)
print("CONFLICTING LISTING IDS")
print("-" * 75)

print(
    f"Found : {len(conflicting_ids)}"
)


# ============================================================
# SHOW DIFFERENCES
# ============================================================

results = []

for listing_id in conflicting_ids:

    group = (
        duplicate_df[
            duplicate_df["listing_id"] == listing_id
        ]
        .copy()
    )

    print("\n" + "=" * 75)
    print(f"LISTING ID: {listing_id}")
    print("=" * 75)

    display_columns = [
        "property_id",
        "listing_id",
        "source_city",
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

    display_columns = [
        field
        for field in display_columns
        if field in group.columns
    ]

    print(
        group[display_columns]
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # Identify fields that actually differ
    # --------------------------------------------------------

    for field in comparison_fields:

        values = group[field].dropna()

        if (
            len(values) > 0
            and values.astype(str).nunique() > 1
        ):

            unique_values = (
                values
                .astype(str)
                .unique()
                .tolist()
            )

            results.append({
                "listing_id": listing_id,
                "field": field,
                "different_values": " | ".join(
                    unique_values
                )
            })


# ============================================================
# SAVE RESULTS
# ============================================================

result_df = pd.DataFrame(results)

result_df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "-" * 75)
print("CONFLICT SUMMARY")
print("-" * 75)

if len(result_df) > 0:

    print(
        result_df
        .groupby("field")
        .size()
        .sort_values(ascending=False)
        .to_string()
    )

else:

    print("No conflicting fields found.")


print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print("Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("INVESTIGATION COMPLETE")
print("=" * 75)