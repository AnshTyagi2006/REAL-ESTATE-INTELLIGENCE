from pathlib import Path
import pandas as pd


# ============================================================
# REAL ESTATE INTELLIGENCE PLATFORM
# MASTER DATASET V2 CLEANING
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "master"
    / "real_estate_master_v1.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "master"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "real_estate_master_v2.csv"
)

REPORT_FILE = (
    PROJECT_ROOT
    / "data"
    / "validation"
    / "master_v2_cleaning_report.csv"
)


print("=" * 75)
print("REAL ESTATE INTELLIGENCE PLATFORM")
print("MASTER DATASET V2 CLEANING")
print("=" * 75)


# ============================================================
# 1. LOAD MASTER V1
# ============================================================

print("\nReading Master V1...")

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

original_rows = len(df)
original_columns = len(df.columns)

print(f"Rows    : {original_rows:,}")
print(f"Columns : {original_columns:,}")


# ============================================================
# 2. BASIC SAFETY CHECK
# ============================================================

print("\n" + "-" * 75)
print("SAFETY CHECK")
print("-" * 75)

if df["listing_id"].isna().any():
    raise ValueError(
        "listing_id contains missing values. "
        "Stopping before deduplication."
    )

if df["property_id"].isna().any():
    raise ValueError(
        "property_id contains missing values. "
        "Stopping before cleaning."
    )

print("listing_id : OK")
print("property_id : OK")


# ============================================================
# 3. INVESTIGATE DUPLICATE LISTING IDS
# ============================================================

print("\n" + "-" * 75)
print("DUPLICATE LISTING ANALYSIS")
print("-" * 75)

listing_counts = df["listing_id"].value_counts()

duplicate_ids = listing_counts[
    listing_counts > 1
]

duplicate_id_count = len(duplicate_ids)

duplicate_row_count = int(
    duplicate_ids.sum()
)

redundant_row_count = (
    duplicate_row_count
    - duplicate_id_count
)

print(
    f"Duplicate listing IDs : "
    f"{duplicate_id_count:,}"
)

print(
    f"Rows involved         : "
    f"{duplicate_row_count:,}"
)

print(
    f"Redundant rows        : "
    f"{redundant_row_count:,}"
)


# ============================================================
# 4. PRESERVE SOURCE INFORMATION
# ============================================================

print("\n" + "-" * 75)
print("CREATING SOURCE SUMMARY")
print("-" * 75)

source_summary = (
    df.groupby("listing_id")["source_city"]
    .apply(
        lambda values: " | ".join(
            sorted(
                set(
                    values
                    .dropna()
                    .astype(str)
                )
            )
        )
    )
    .rename("source_cities")
    .reset_index()
)

df = df.merge(
    source_summary,
    on="listing_id",
    how="left"
)

print("Added column: source_cities")


# ============================================================
# 5. MARK DUPLICATE STATUS
# ============================================================

df["duplicate_listing"] = (
    df["listing_id"]
    .duplicated(keep=False)
)

print(
    "Added column: duplicate_listing"
)


# ============================================================
# 6. REMOVE REDUNDANT LISTING COPIES
# ============================================================

print("\n" + "-" * 75)
print("DEDUPLICATION")
print("-" * 75)

before_deduplication = len(df)

# Keep the first occurrence of each listing_id.
df = df.drop_duplicates(
    subset=["listing_id"],
    keep="first"
).copy()

after_deduplication = len(df)

removed_rows = (
    before_deduplication
    - after_deduplication
)

print(
    f"Rows before : "
    f"{before_deduplication:,}"
)

print(
    f"Rows after  : "
    f"{after_deduplication:,}"
)

print(
    f"Rows removed: "
    f"{removed_rows:,}"
)


# ============================================================
# 7. FIX INVALID TOTAL_FLOORS
# ============================================================

print("\n" + "-" * 75)
print("TOTAL_FLOORS CHECK")
print("-" * 75)

invalid_floor_mask = (
    (df["total_floors"] < 0)
    |
    (df["total_floors"] > 200)
)

invalid_floor_count = int(
    invalid_floor_mask.sum()
)

print(
    f"Invalid total_floors values : "
    f"{invalid_floor_count}"
)

if invalid_floor_count > 0:

    print(
        "\nValues being converted to missing:"
    )

    print(
        df.loc[
            invalid_floor_mask,
            [
                "property_id",
                "listing_id",
                "city",
                "locality",
                "floor",
                "total_floors"
            ]
        ].to_string(index=False)
    )

    df.loc[
        invalid_floor_mask,
        "total_floors"
    ] = pd.NA

    print(
        "\nInvalid total_floors values "
        "converted to missing."
    )

else:

    print(
        "No invalid total_floors values found."
    )


# ============================================================
# 8. RESET INDEX
# ============================================================

df.reset_index(
    drop=True,
    inplace=True
)


# ============================================================
# 9. FINAL SAFETY CHECKS
# ============================================================

print("\n" + "-" * 75)
print("FINAL SAFETY CHECKS")
print("-" * 75)

final_rows = len(df)
final_columns = len(df.columns)

duplicate_listing_ids_after = (
    df["listing_id"]
    .duplicated()
    .sum()
)

duplicate_property_ids_after = (
    df["property_id"]
    .duplicated()
    .sum()
)

invalid_total_floors_after = (
    (
        (df["total_floors"] < 0)
        |
        (df["total_floors"] > 200)
    )
    .fillna(False)
    .sum()
)


print(
    f"Final rows                 : "
    f"{final_rows:,}"
)

print(
    f"Final columns              : "
    f"{final_columns:,}"
)

print(
    f"Duplicate listing IDs      : "
    f"{duplicate_listing_ids_after}"
)

print(
    f"Duplicate property IDs     : "
    f"{duplicate_property_ids_after}"
)

print(
    f"Invalid total_floors      : "
    f"{invalid_total_floors_after}"
)


# ============================================================
# 10. HARD VALIDATION
# ============================================================

expected_rows = (
    original_rows
    - redundant_row_count
)

if final_rows != expected_rows:

    raise ValueError(
        f"Unexpected final row count. "
        f"Expected {expected_rows}, "
        f"got {final_rows}."
    )

if duplicate_listing_ids_after != 0:

    raise ValueError(
        "Duplicate listing IDs still exist."
    )

if duplicate_property_ids_after != 0:

    raise ValueError(
        "Duplicate property IDs still exist."
    )

if invalid_total_floors_after != 0:

    raise ValueError(
        "Invalid total_floors values still exist."
    )

print("\nAll safety checks passed.")


# ============================================================
# 11. SAVE MASTER V2
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print("\n" + "-" * 75)
print("MASTER V2 SAVED")
print("-" * 75)

print(
    f"Output:\n{OUTPUT_FILE}"
)


# ============================================================
# 12. SAVE CLEANING REPORT
# ============================================================

report = pd.DataFrame([
    {
        "operation": "input_rows",
        "value": original_rows
    },
    {
        "operation": "input_columns",
        "value": original_columns
    },
    {
        "operation": "duplicate_listing_ids",
        "value": duplicate_id_count
    },
    {
        "operation": "duplicate_rows_involved",
        "value": duplicate_row_count
    },
    {
        "operation": "redundant_rows_removed",
        "value": removed_rows
    },
    {
        "operation": "invalid_total_floors_fixed",
        "value": invalid_floor_count
    },
    {
        "operation": "final_rows",
        "value": final_rows
    },
    {
        "operation": "final_columns",
        "value": final_columns
    }
])

report.to_csv(
    REPORT_FILE,
    index=False
)

print(
    f"\nCleaning report:\n{REPORT_FILE}"
)


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 75)
print("MASTER DATASET V2 CLEANING COMPLETE")
print("=" * 75)

print("\nImportant:")
print("- Master V1 was NOT modified.")
print("- No missing prices were filled.")
print("- No missing areas were filled.")
print("- No bedroom values were guessed.")
print("- No coded fields were interpreted.")
print("- No city/locality values were changed.")
print("- Only confirmed duplicate listings were deduplicated.")
print("- Invalid total_floors = 550 was converted to missing.")