from __future__ import annotations

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


COLUMNS_TO_CHECK = [
    "city",
    "locality",
    "property_type",
    "product_type",
    "configuration",
    "bedrooms",
    "bathrooms",
    "furnishing",
    "status",
    "listing_category",
    "listing_type",
    "seller_type",
    "seller_class",
    "area_basis",
    "parking",
    "reserved_parking",
    "facing",
    "overlooking",
]


def inspect_column(df: pd.DataFrame, column: str):

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
    }

    if len(non_null) > 0:

        value_counts = (
            non_null
            .astype(str)
            .str.strip()
            .value_counts()
            .head(20)
        )

        result["top_values"] = value_counts.to_dict()

    else:

        result["top_values"] = {}

    return result


def main():

    print("\n" + "=" * 75)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("DATA VALUE INVESTIGATION")
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

    results = []

    for column in COLUMNS_TO_CHECK:

        result = inspect_column(
            df,
            column
        )

        if result is None:

            print(
                f"\n[NOT FOUND] {column}"
            )

            continue

        results.append(result)

        print("\n" + "-" * 75)

        print(
            f"Column        : {column}"
        )

        print(
            f"Data type     : {result['data_type']}"
        )

        print(
            f"Non-null      : {result['non_null']:,}"
        )

        print(
            f"Missing       : {result['missing']:,}"
        )

        print(
            f"Unique values : {result['unique_values']:,}"
        )

        print("\nTop values:")

        for value, count in result["top_values"].items():

            print(
                f"  {value!r:<40} {count:,}"
            )

    # Save a simple summary CSV.

    summary_rows = []

    for result in results:

        summary_rows.append({
            "column": result["column"],
            "data_type": result["data_type"],
            "total_rows": result["total_rows"],
            "non_null": result["non_null"],
            "missing": result["missing"],
            "unique_values": result["unique_values"],
        })

    summary_df = pd.DataFrame(
        summary_rows
    )

    summary_file = (
        OUTPUT_DIR
        / "value_investigation_summary.csv"
    )

    summary_df.to_csv(
        summary_file,
        index=False
    )

    print("\n" + "=" * 75)

    print(
        f"Investigation summary saved to:\n"
        f"{summary_file}"
    )

    print(
        "\nNo source data was modified."
    )

    print("=" * 75)


if __name__ == "__main__":
    main()