from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT
    / "data"
    / "combined"
    / "real_estate_combined_raw.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "investigation"
)


# These are the columns whose values look coded or encoded.
CODED_COLUMNS = [
    "furnishing",
    "facing",
    "listing_type",
    "listing_category",
    "seller_class",
    "property_age_code",
    "parking",
    "reserved_parking",
    "overlooking",
]


# Readable columns that can help us understand the codes.
CONTEXT_COLUMNS = [
    "city",
    "locality",
    "property_type",
    "product_type",
    "configuration",
    "bedrooms",
    "bathrooms",
    "status",
    "seller_type",
    "area_basis",
    "property_age",
]


def get_value_counts(df: pd.DataFrame, column: str):

    if column not in df.columns:
        return []

    series = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    counts = series.value_counts()

    results = []

    for value, count in counts.items():

        results.append({
            "value": value,
            "count": int(count),
            "percentage": round(
                (count / len(series)) * 100,
                2
            )
        })

    return results


def inspect_coded_column(
    df: pd.DataFrame,
    column: str
):

    if column not in df.columns:
        return None

    series = df[column]

    non_null = series.dropna()

    result = {
        "column": column,
        "data_type": str(series.dtype),
        "total_rows": len(series),
        "non_null": int(series.notna().sum()),
        "missing": int(series.isna().sum()),
        "unique_values": int(series.nunique(dropna=True)),
        "values": get_value_counts(df, column),
    }

    return result


def inspect_relationship(
    df: pd.DataFrame,
    coded_column: str,
    context_column: str,
    max_codes: int = 15,
    max_context_values: int = 10,
):

    if coded_column not in df.columns:
        return None

    if context_column not in df.columns:
        return None

    working = df[
        [coded_column, context_column]
    ].copy()

    working = working.dropna(
        subset=[coded_column]
    )

    if working.empty:
        return None

    working[coded_column] = (
        working[coded_column]
        .astype(str)
        .str.strip()
    )

    results = []

    top_codes = (
        working[coded_column]
        .value_counts()
        .head(max_codes)
        .index
    )

    for code in top_codes:

        subset = working[
            working[coded_column] == code
        ]

        context_values = (
            subset[context_column]
            .dropna()
            .astype(str)
            .str.strip()
            .value_counts()
            .head(max_context_values)
        )

        results.append({
            "coded_column": coded_column,
            "code": code,
            "code_count": int(len(subset)),
            "context_column": context_column,
            "context_values": {
                str(value): int(count)
                for value, count
                in context_values.items()
            }
        })

    return results


def main():

    print("\n" + "=" * 75)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("CODED VALUE INVESTIGATION")
    print("=" * 75)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"\nInput file not found:\n{INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nReading combined dataset...")

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

    # ---------------------------------------------------------
    # PART 1: VALUE LIST
    # ---------------------------------------------------------

    print("\n" + "=" * 75)
    print("PART 1 — CODED COLUMN VALUES")
    print("=" * 75)

    value_results = {}

    for column in CODED_COLUMNS:

        result = inspect_coded_column(
            df,
            column
        )

        if result is None:
            continue

        value_results[column] = result

        print("\n" + "-" * 75)

        print(
            f"Column       : {column}"
        )

        print(
            f"Non-null     : {result['non_null']:,}"
        )

        print(
            f"Missing      : {result['missing']:,}"
        )

        print(
            f"Unique       : {result['unique_values']:,}"
        )

        print("\nValues:")

        for item in result["values"][:50]:

            print(
                f"  {item['value']!r:<35}"
                f"{item['count']:>7,} "
                f"({item['percentage']:>6.2f}%)"
            )

    # ---------------------------------------------------------
    # PART 2: RELATIONSHIPS
    # ---------------------------------------------------------

    print("\n" + "=" * 75)
    print("PART 2 — RELATIONSHIP INVESTIGATION")
    print("=" * 75)

    relationship_results = []

    for coded_column in CODED_COLUMNS:

        if coded_column not in df.columns:
            continue

        for context_column in CONTEXT_COLUMNS:

            if context_column not in df.columns:
                continue

            relationships = inspect_relationship(
                df,
                coded_column,
                context_column
            )

            if relationships:
                relationship_results.extend(
                    relationships
                )

    # ---------------------------------------------------------
    # Save JSON
    # ---------------------------------------------------------

    json_file = (
        OUTPUT_DIR
        / "coded_value_investigation.json"
    )

    output = {
        "dataset": {
            "rows": len(df),
            "columns": len(df.columns),
        },
        "coded_columns": value_results,
        "relationships": relationship_results,
        "note": (
            "Investigation only. "
            "No source data was modified. "
            "Code meanings were not assumed."
        )
    }

    with open(
        json_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\n" + "=" * 75)

    print(
        f"Investigation saved to:\n"
        f"{json_file}"
    )

    print(
        "\nNo source data was modified."
    )

    print("=" * 75)


if __name__ == "__main__":
    main()