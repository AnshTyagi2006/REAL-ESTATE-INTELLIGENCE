from __future__ import annotations

import pandas as pd
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT
    / "data"
    / "schema"
    / "source_column_mapping.csv"
)


def main():

    print("\n" + "=" * 75)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("SOURCE COLUMN REVIEW")
    print("=" * 75)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"\nMapping file not found:\n{INPUT_FILE}\n\n"
            f"Run build_canonical_schema.py first."
        )

    df = pd.read_csv(INPUT_FILE)

    review_df = df[
        df["classification"] != "CANONICAL"
    ].copy()

    print(f"\nTotal source columns          : {len(df)}")
    print(f"Columns requiring review     : {len(review_df)}")

    print("\n" + "-" * 75)
    print("COLUMNS REQUIRING REVIEW")
    print("-" * 75)

    for classification in [
        "UNMAPPED_REVIEW",
        "DERIVED_OR_ANALYTICAL",
        "SOURCE_METADATA",
        "ALTERNATE_REPRESENTATION",
    ]:

        subset = review_df[
            review_df["classification"] == classification
        ]

        if subset.empty:
            continue

        print(
            f"\n[{classification}] "
            f"({len(subset)} columns)"
        )

        for _, row in subset.iterrows():

            print(
                f"\n  Column       : {row['source_column']}"
            )

            print(
                f"  Normalized   : "
                f"{row['normalized_source_column']}"
            )

            print(
                f"  Decision     : "
                f"{row['decision']}"
            )

            print(
                f"  Notes        : "
                f"{row['notes']}"
            )

    print("\n" + "-" * 75)
    print("REVIEW COMPLETE")
    print("-" * 75)

    print(
        "\nNo data was modified."
    )

    print(
        "\nThe purpose of this step is to decide which "
        "source-specific columns should be retained, "
        "transformed, or excluded before standardization."
    )

    print("=" * 75)


if __name__ == "__main__":
    main()