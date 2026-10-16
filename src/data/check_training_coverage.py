from pathlib import Path
import pandas as pd


# ============================================================
# TRAINING COVERAGE CHECK
# Purpose:
# Check whether properties outside the current 3,073
# price + valuation-area records can safely be added
# to the ML valuation training population.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = PROJECT_ROOT / "data" / "master" / "real_estate_master_v4.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "investigation"
OUTPUT_FILE = OUTPUT_DIR / "training_coverage_report.csv"


# ------------------------------------------------------------
# 1. Load data
# ------------------------------------------------------------

df = pd.read_csv(INPUT_FILE, low_memory=False)

print("=" * 70)
print("TRAINING COVERAGE CHECK")
print("=" * 70)

print(f"Total properties              : {len(df):,}")


# ------------------------------------------------------------
# 2. Identify price availability
# ------------------------------------------------------------

has_price = (
    df["asking_price_inr"].notna()
    & (df["asking_price_inr"] > 0)
)

has_valuation_area = (
    df["valuation_area_sqft"].notna()
    & (df["valuation_area_sqft"] > 0)
)

price_and_area = has_price & has_valuation_area
price_only = has_price & ~has_valuation_area
area_only = ~has_price & has_valuation_area
neither = ~has_price & ~has_valuation_area


print("\nCURRENT COVERAGE")
print("-" * 70)
print(f"Price + valuation area         : {price_and_area.sum():,}")
print(f"Price only                     : {price_only.sum():,}")
print(f"Area only                      : {area_only.sum():,}")
print(f"Neither                        : {neither.sum():,}")


# ------------------------------------------------------------
# 3. Check ALL alternative area fields
# ------------------------------------------------------------

area_candidates = [
    "area_sqft",
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft",
    "carpet_area_sqft",
    "builtup_area_sqft",
    "superbuiltup_area_sqft",
]

existing_area_candidates = [
    col for col in area_candidates if col in df.columns
]

print("\nALTERNATIVE AREA AVAILABILITY")
print("-" * 70)

for col in existing_area_candidates:

    available = (
        df[col].notna()
        & (pd.to_numeric(df[col], errors="coerce") > 0)
    )

    price_only_available = available & price_only

    print(
        f"{col:<30} "
        f"all={available.sum():>5,} | "
        f"price-only={price_only_available.sum():>5,}"
    )


# ------------------------------------------------------------
# 4. Find price-only properties with ANY area information
# ------------------------------------------------------------

numeric_area_data = pd.DataFrame(index=df.index)

for col in existing_area_candidates:
    numeric_area_data[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

has_any_alternative_area = numeric_area_data.notna().any(axis=1)

price_only_with_any_area = (
    price_only & has_any_alternative_area
)

print("\nEXPANSION OPPORTUNITY")
print("-" * 70)

print(
    "Price-only properties with another area field : "
    f"{price_only_with_any_area.sum():,}"
)

print(
    "Price-only properties with NO area at all     : "
    f"{(price_only & ~has_any_alternative_area).sum():,}"
)


# ------------------------------------------------------------
# 5. Check which cities could gain training records
# ------------------------------------------------------------

city_summary = (
    df.loc[price_only]
    .assign(
        has_any_area=has_any_alternative_area.loc[price_only]
    )
    .groupby("city", dropna=False)
    .agg(
        price_only_records=("asking_price_inr", "size"),
        price_only_with_any_area=("has_any_area", "sum"),
    )
    .reset_index()
)

city_summary["potential_additions"] = (
    city_summary["price_only_with_any_area"]
)

city_summary = city_summary.sort_values(
    "potential_additions",
    ascending=False
)

print("\nPRICE-ONLY RECORDS BY CITY")
print("-" * 70)

print(city_summary.to_string(index=False))


# ------------------------------------------------------------
# 6. Check area source combinations
# ------------------------------------------------------------

source_counts = {}

for col in existing_area_candidates:

    count = (
        price_only
        & numeric_area_data[col].notna()
    ).sum()

    source_counts[col] = int(count)

source_df = pd.DataFrame(
    list(source_counts.items()),
    columns=["area_field", "price_only_records"]
)

# ------------------------------------------------------------
# 7. Save compact report
# ------------------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

city_summary.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\nREPORT SAVED")
print("-" * 70)
print(OUTPUT_FILE)

print("\nFINAL INTERPRETATION")
print("-" * 70)

if price_only_with_any_area.sum() > 0:
    print(
        "Some price-only properties contain alternative area information."
    )
    print(
        "These require semantic validation before adding them to ML training."
    )
else:
    print(
        "No price-only properties contain a usable alternative area field."
    )
    print(
        "The current 3,073 records remain the clean supervised training population."
    )

print("=" * 70)