from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT
    / "data"
    / "master"
    / "real_estate_master_v1.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "validation"
)


def check_range(df, column, minimum=None, maximum=None):

    if column not in df.columns:
        return {
            "column": column,
            "status": "NOT_FOUND"
        }

    series = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    invalid = pd.Series(
        False,
        index=df.index
    )

    if minimum is not None:
        invalid |= series < minimum

    if maximum is not None:
        invalid |= series > maximum

    return {
        "column": column,
        "status": "CHECKED",
        "non_null": int(series.notna().sum()),
        "invalid_count": int(invalid.sum()),
        "minimum": (
            float(series.min())
            if series.notna().any()
            else None
        ),
        "maximum": (
            float(series.max())
            if series.notna().any()
            else None
        ),
    }


def main():

    print("\n" + "=" * 75)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("MASTER DATASET VALIDATION")
    print("=" * 75)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"\nMaster dataset not found:\n{INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nReading master dataset...")

    df = pd.read_csv(
        INPUT_FILE,
        low_memory=False
    )

    print(
        f"Rows    : {len(df):,}"
    )

    print(
        f"Columns : {len(df.columns)}"
    )

    results = []

    # ---------------------------------------------------------
    # 1. Property ID
    # ---------------------------------------------------------

    print("\n" + "-" * 75)
    print("1. PROPERTY ID CHECK")
    print("-" * 75)

    property_id_count = (
        df["property_id"].notna().sum()
    )

    duplicate_property_ids = (
        df["property_id"].duplicated().sum()
    )

    print(
        f"Non-null IDs      : "
        f"{property_id_count:,}"
    )

    print(
        f"Duplicate IDs     : "
        f"{duplicate_property_ids:,}"
    )

    results.append({
        "check": "property_id_duplicates",
        "value": int(duplicate_property_ids)
    })

    # ---------------------------------------------------------
    # 2. Listing ID duplicates
    # ---------------------------------------------------------

    print("\n" + "-" * 75)
    print("2. LISTING ID CHECK")
    print("-" * 75)

    if "listing_id" in df.columns:

        duplicate_listing_ids = (
            df["listing_id"]
            .dropna()
            .duplicated()
            .sum()
        )

        print(
            f"Duplicate listing IDs : "
            f"{duplicate_listing_ids:,}"
        )

        results.append({
            "check": "listing_id_duplicates",
            "value": int(duplicate_listing_ids)
        })

    # ---------------------------------------------------------
    # 3. Important numeric fields
    # ---------------------------------------------------------

    print("\n" + "-" * 75)
    print("3. NUMERIC RANGE CHECKS")
    print("-" * 75)

    checks = [
        ("price_inr", 0, None),
        ("price_per_sqft", 0, None),
        ("area_sqft", 0, None),
        ("bedrooms", 0, 20),
        ("bathrooms", 0, 20),
        ("balconies", 0, 20),
        ("floor", 0, None),
        ("total_floors", 0, 200),
        ("latitude", -90, 90),
        ("longitude", -180, 180),
    ]

    for column, minimum, maximum in checks:

        result = check_range(
            df,
            column,
            minimum,
            maximum
        )

        results.append({
            "check": f"{column}_range",
            **result
        })

        if result["status"] == "NOT_FOUND":

            print(
                f"{column:<25} NOT FOUND"
            )

        else:

            print(
                f"{column:<25}"
                f"invalid={result['invalid_count']:,} "
                f"min={result['minimum']} "
                f"max={result['maximum']}"
            )

    # ---------------------------------------------------------
    # 4. Missing important fields
    # ---------------------------------------------------------

    print("\n" + "-" * 75)
    print("4. IMPORTANT FIELD MISSINGNESS")
    print("-" * 75)

    important_columns = [
        "property_id",
        "listing_id",
        "city",
        "locality",
        "latitude",
        "longitude",
        "property_type",
        "bedrooms",
        "area_sqft",
        "price_inr",
        "price_per_sqft",
    ]

    missing_rows = []

    for column in important_columns:

        if column not in df.columns:
            continue

        missing = int(
            df[column].isna().sum()
        )

        percentage = (
            missing
            / len(df)
            * 100
        )

        print(
            f"{column:<25}"
            f"missing={missing:,} "
            f"({percentage:.2f}%)"
        )

        missing_rows.append({
            "column": column,
            "missing": missing,
            "missing_percentage": round(
                percentage,
                2
            )
        })

    # ---------------------------------------------------------
    # 5. Floor consistency
    # ---------------------------------------------------------

    print("\n" + "-" * 75)
    print("5. FLOOR CONSISTENCY")
    print("-" * 75)

    if (
        "floor" in df.columns
        and "total_floors" in df.columns
    ):

        floor = pd.to_numeric(
            df["floor"],
            errors="coerce"
        )

        total_floors = pd.to_numeric(
            df["total_floors"],
            errors="coerce"
        )

        invalid_floor = (
            floor.notna()
            & total_floors.notna()
            & (floor > total_floors)
        )

        print(
            f"floor > total_floors : "
            f"{invalid_floor.sum():,}"
        )

        results.append({
            "check": "floor_greater_than_total_floors",
            "value": int(invalid_floor.sum())
        })

    # ---------------------------------------------------------
    # 6. Save reports
    # ---------------------------------------------------------

    results_file = (
        OUTPUT_DIR
        / "validation_results.csv"
    )

    missing_file = (
        OUTPUT_DIR
        / "important_fields_missing.csv"
    )

    pd.DataFrame(
        results
    ).to_csv(
        results_file,
        index=False
    )

    pd.DataFrame(
        missing_rows
    ).to_csv(
        missing_file,
        index=False
    )

    print("\n" + "=" * 75)

    print(
        f"Validation results:\n"
        f"{results_file}"
    )

    print(
        f"\nMissingness report:\n"
        f"{missing_file}"
    )

    print(
        "\nNo master data was modified."
    )

    print("=" * 75)


if __name__ == "__main__":
    main()