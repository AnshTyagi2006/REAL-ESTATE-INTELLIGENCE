from pathlib import Path
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
print("COMPARABLE PROPERTY ENGINE — DATA READINESS")
print("=" * 70)

print(f"\nTotal properties: {len(df):,}")


# ============================================================
# 3. FIELDS NEEDED
# ============================================================

comparable_features = [
    "city",
    "locality",
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "property_type",
    "asking_price_inr",
]


# ============================================================
# 4. FIELD COVERAGE
# ============================================================

print("\n" + "-" * 70)
print("FIELD COVERAGE")
print("-" * 70)

for column in comparable_features:

    available = df[column].notna().sum()
    missing = df[column].isna().sum()

    percentage = (
        available / len(df)
    ) * 100

    print(
        f"{column:<25} "
        f"{available:>6,} available | "
        f"{missing:>6,} missing | "
        f"{percentage:>6.2f}% usable"
    )


# ============================================================
# 5. COMPLETE COMPARABLE RECORDS
# ============================================================

complete_mask = df[
    comparable_features
].notna().all(axis=1)

complete_count = complete_mask.sum()

print("\n" + "-" * 70)
print("COMPLETE COMPARABLE RECORDS")
print("-" * 70)

print(
    f"Properties with all required fields: "
    f"{complete_count:,}"
)

print(
    f"Percentage of dataset: "
    f"{complete_count / len(df) * 100:.2f}%"
)


# ============================================================
# 6. LOCALITY COVERAGE
# ============================================================

locality_counts = (
    df["locality"]
    .dropna()
    .value_counts()
)

print("\n" + "-" * 70)
print("LOCALITY COVERAGE")
print("-" * 70)

print(
    f"Unique localities: "
    f"{df['locality'].nunique():,}"
)

print(
    f"Localities with 1 property: "
    f"{(locality_counts == 1).sum():,}"
)

print(
    f"Localities with 2+ properties: "
    f"{(locality_counts >= 2).sum():,}"
)

print(
    f"Localities with 5+ properties: "
    f"{(locality_counts >= 5).sum():,}"
)

print(
    f"Localities with 10+ properties: "
    f"{(locality_counts >= 10).sum():,}"
)

print(
    f"Localities with 20+ properties: "
    f"{(locality_counts >= 20).sum():,}"
)


# ============================================================
# 7. TOP LOCALITIES
# ============================================================

print("\n" + "-" * 70)
print("TOP 15 LOCALITIES BY PROPERTY COUNT")
print("-" * 70)

print(
    locality_counts.head(15).to_string()
)


# ============================================================
# 8. CITY COVERAGE
# ============================================================

print("\n" + "-" * 70)
print("CITY COVERAGE")
print("-" * 70)

city_counts = (
    df["city"]
    .dropna()
    .value_counts()
)

print(
    city_counts.to_string()
)


# ============================================================
# 9. COORDINATE COVERAGE
# ============================================================

coordinates_available = df[
    ["latitude", "longitude"]
].notna().all(axis=1).sum()

print("\n" + "-" * 70)
print("GEOGRAPHIC COVERAGE")
print("-" * 70)

print(
    f"Properties with latitude + longitude: "
    f"{coordinates_available:,}"
)

print(
    f"Coordinate coverage: "
    f"{coordinates_available / len(df) * 100:.2f}%"
)


# ============================================================
# 10. PROPERTY TYPE COVERAGE
# ============================================================

print("\n" + "-" * 70)
print("PROPERTY TYPE COVERAGE")
print("-" * 70)

print(
    df["property_type"]
    .value_counts(dropna=False)
    .head(20)
    .to_string()
)


# ============================================================
# 11. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print(
    "\nThe Comparable Engine will primarily use:"
)

print("✓ Locality")
print("✓ Geographic coordinates")
print("✓ Area")
print("✓ Bedrooms")
print("✓ Bathrooms")
print("✓ Property type")
print("✓ Asking price")

print(
    "\nData-readiness profiling completed."
)