from pathlib import Path
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MASTER_FILE = PROJECT_ROOT / "data" / "master" / "real_estate_master_v1.csv"

OUTPUT_DIR = PROJECT_ROOT / "data" / "investigation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "validation_issue_records.csv"


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("VALIDATION ISSUE INVESTIGATION")
print("=" * 75)

print("\nReading master dataset...")

df = pd.read_csv(MASTER_FILE, low_memory=False)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df):,}")


# ============================================================
# 1. SUSPICIOUS TOTAL FLOORS
# ============================================================

print("\n" + "-" * 75)
print("1. SUSPICIOUS TOTAL_FLOORS")
print("-" * 75)

suspicious_floors = df[
    (df["total_floors"] < 0) |
    (df["total_floors"] > 200)
].copy()

print(f"Suspicious rows : {len(suspicious_floors)}")

if len(suspicious_floors) > 0:
    columns = [
        "property_id",
        "listing_id",
        "city",
        "locality",
        "configuration",
        "property_type",
        "bedrooms",
        "floor",
        "total_floors",
        "price_inr",
        "price_per_sqft",
        "area_sqft",
        "latitude",
        "longitude",
    ]

    columns = [c for c in columns if c in suspicious_floors.columns]

    print("\nSuspicious records:")
    print(
        suspicious_floors[columns]
        .to_string(index=False)
    )


# ============================================================
# 2. DUPLICATE LISTING IDS
# ============================================================

print("\n" + "-" * 75)
print("2. DUPLICATE LISTING IDS")
print("-" * 75)

listing_counts = (
    df["listing_id"]
    .value_counts()
)

duplicate_listing_ids = listing_counts[
    listing_counts > 1
].index

duplicate_rows = df[
    df["listing_id"].isin(duplicate_listing_ids)
].copy()

print(f"Duplicate listing IDs : {len(duplicate_listing_ids):,}")
print(f"Rows involved         : {len(duplicate_rows):,}")

duplicate_columns = [
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

duplicate_columns = [
    c for c in duplicate_columns
    if c in duplicate_rows.columns
]

print("\nFirst duplicate groups:")

for listing_id, group in (
    duplicate_rows
    .groupby("listing_id", sort=False)
    .head(20)
    .groupby("listing_id", sort=False)
):
    print("\nListing ID:", listing_id)
    print(
        group[duplicate_columns]
        .to_string(index=False)
    )

    # Only display the first 10 duplicate groups
    if list(
        duplicate_rows
        .groupby("listing_id", sort=False)
        .groups
        .keys()
    ).index(listing_id) >= 9:
        break


# ============================================================
# 3. SAVE ALL SUSPICIOUS RECORDS
# ============================================================

frames = []

if len(suspicious_floors) > 0:
    temp = suspicious_floors.copy()
    temp["issue_type"] = "suspicious_total_floors"
    frames.append(temp)

if len(duplicate_rows) > 0:
    temp = duplicate_rows.copy()
    temp["issue_type"] = "duplicate_listing_id"
    frames.append(temp)


if frames:
    investigation_df = pd.concat(
        frames,
        ignore_index=True
    )

    investigation_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n" + "-" * 75)
    print("INVESTIGATION FILE")
    print("-" * 75)

    print(f"Saved to:")
    print(OUTPUT_FILE)

else:
    print("\nNo validation issues found.")


print("\n" + "=" * 75)
print("INVESTIGATION COMPLETE")
print("=" * 75)