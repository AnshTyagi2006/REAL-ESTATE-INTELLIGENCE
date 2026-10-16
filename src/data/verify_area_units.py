import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "master" / "real_estate_master_v2.csv"
OUTPUT_FILE = BASE_DIR / "data" / "investigation" / "area_unit_verification.csv"

SQM_TO_SQFT = 10.7639

print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("AREA UNIT VERIFICATION")
print("=" * 75)

df = pd.read_csv(INPUT_FILE, low_memory=False)

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df):,}")

# ---------------------------------------------------------
# Keep rows where all relevant fields exist
# ---------------------------------------------------------

cols = [
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft"
]

work = df[cols].dropna().copy()

print("\n" + "-" * 75)
print("BASIC RANGE CHECK")
print("-" * 75)

print(f"Rows with all three fields : {len(work):,}")

# ---------------------------------------------------------
# Convert min/max from sqm to sqft
# ---------------------------------------------------------

work["min_converted_sqft"] = (
    work["area_min_sqft"] * SQM_TO_SQFT
)

work["max_converted_sqft"] = (
    work["area_max_sqft"] * SQM_TO_SQFT
)

# ---------------------------------------------------------
# Difference between model area and converted values
# ---------------------------------------------------------

work["min_difference_pct"] = (
    abs(work["area_sqft_model"] - work["min_converted_sqft"])
    / work["area_sqft_model"]
) * 100

work["max_difference_pct"] = (
    abs(work["area_sqft_model"] - work["max_converted_sqft"])
    / work["area_sqft_model"]
) * 100

# ---------------------------------------------------------
# Exact / approximate matching
# ---------------------------------------------------------

for tolerance in [1, 2, 5]:

    min_match = (
        work["min_difference_pct"] <= tolerance
    ).sum()

    max_match = (
        work["max_difference_pct"] <= tolerance
    ).sum()

    print(
        f"\nTolerance {tolerance}%:"
    )

    print(
        f"  Model ≈ converted MIN : "
        f"{min_match:,} "
        f"({min_match / len(work) * 100:.2f}%)"
    )

    print(
        f"  Model ≈ converted MAX : "
        f"{max_match:,} "
        f"({max_match / len(work) * 100:.2f}%)"
    )

# ---------------------------------------------------------
# Check whether min/max are actually different
# ---------------------------------------------------------

work["range_difference_sqm"] = (
    work["area_max_sqft"] -
    work["area_min_sqft"]
)

different_range = (
    work["range_difference_sqm"].abs() > 0.0001
)

print("\n" + "-" * 75)
print("MIN / MAX RANGE INVESTIGATION")
print("-" * 75)

print(
    f"MIN == MAX : "
    f"{(~different_range).sum():,} "
    f"({(~different_range).mean() * 100:.2f}%)"
)

print(
    f"MIN != MAX : "
    f"{different_range.sum():,} "
    f"({different_range.mean() * 100:.2f}%)"
)

# ---------------------------------------------------------
# For actual ranges, check whether model is inside range
# ---------------------------------------------------------

range_rows = work[different_range].copy()

if len(range_rows) > 0:

    range_rows["model_inside_range"] = (
        (range_rows["area_sqft_model"] >= range_rows["min_converted_sqft"])
        &
        (range_rows["area_sqft_model"] <= range_rows["max_converted_sqft"])
    )

    print("\n" + "-" * 75)
    print("MODEL AREA INSIDE CONVERTED RANGE")
    print("-" * 75)

    inside = range_rows["model_inside_range"].sum()

    print(
        f"Rows with actual range : {len(range_rows):,}"
    )

    print(
        f"Model inside range     : "
        f"{inside:,} "
        f"({inside / len(range_rows) * 100:.2f}%)"
    )

# ---------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------

print("\n" + "-" * 75)
print("UNIT CONVERSION CHECK")
print("-" * 75)

print("\nFirst 20 examples:\n")

display_cols = [
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft",
    "min_converted_sqft",
    "max_converted_sqft",
    "min_difference_pct",
    "max_difference_pct"
]

print(
    work[display_cols]
    .head(20)
    .to_string(index=False)
)

# ---------------------------------------------------------
# Save detailed output
# ---------------------------------------------------------

work.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("OUTPUT")
print("-" * 75)

print(f"Saved to:")
print(OUTPUT_FILE)

print("\n" + "=" * 75)
print("AREA UNIT VERIFICATION COMPLETE")
print("=" * 75)

print("\nMaster V2 was NOT modified.")