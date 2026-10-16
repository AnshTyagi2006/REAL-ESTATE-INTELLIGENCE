from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


# ============================================================
# 1. PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "data" / "combined" / "real_estate_combined_raw.csv"

SCHEMA_FILE = ROOT / "schema" / "canonical_schema.json"

OUTPUT_DIR = ROOT / "data" / "schema"


# ============================================================
# 2. NORMALIZE COLUMN NAMES
# ============================================================

def normalize_column(column_name: str) -> str:
    """
    Convert a source column name into a normalized form.

    Example:
        'Price Per Sqft' -> 'price_per_sqft'
        'LOCALIZED_AREA' -> 'localized_area'
    """

    column_name = str(column_name).strip().lower()

    column_name = re.sub(
        r"[^a-z0-9]+",
        "_",
        column_name
    )

    return column_name.strip("_")


# ============================================================
# 3. CLASSIFY SOURCE COLUMNS THAT ARE NOT
#    DIRECTLY MAPPED TO THE CANONICAL SCHEMA
# ============================================================

def classify_unmapped_column(column_name: str) -> tuple[str, str]:

    column = normalize_column(column_name)

    # --------------------------------------------------------
    # Derived / analytical fields
    # --------------------------------------------------------

    derived_keywords = [
        "log_",
        "floor_ratio",
        "quality_flag_count",
        "valuation_",
        "model_",
        "price_lakh",
        "price_crore",
    ]

    # --------------------------------------------------------
    # Alternate representations
    # --------------------------------------------------------

    alternate_keywords = [
        "localized_",
        "area_sqft_model",
        "price_lakh",
        "price_crore",
        "log_price",
        "log_price_per_sqft",
    ]

    # --------------------------------------------------------
    # Source / extraction metadata
    # --------------------------------------------------------

    metadata_keywords = [
        "source",
        "scraped",
        "posting",
        "posted",
        "updated",
        "update",
        "seller_name",
        "seller_company",
        "source_page",
        "description",
        "index",
    ]

    if any(keyword in column for keyword in derived_keywords):

        return (
            "DERIVED_OR_ANALYTICAL",
            "Likely derived or analytical representation."
        )

    if any(keyword in column for keyword in alternate_keywords):

        return (
            "ALTERNATE_REPRESENTATION",
            "Likely alternate/source-specific representation."
        )

    if any(keyword in column for keyword in metadata_keywords):

        return (
            "SOURCE_METADATA",
            "Source, extraction or provenance information."
        )

    return (
        "UNMAPPED_REVIEW",
        "Requires manual semantic review."
    )


# ============================================================
# 4. MAIN FUNCTION
# ============================================================

def main():

    print("\n" + "=" * 70)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("CANONICAL SCHEMA AUDIT")
    print("=" * 70)

    # --------------------------------------------------------
    # Check input files
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"\nCombined dataset was not found:\n"
            f"{INPUT_FILE}\n\n"
            f"Run combine_datasets.py first."
        )

    if not SCHEMA_FILE.exists():

        raise FileNotFoundError(
            f"\nCanonical schema file was not found:\n"
            f"{SCHEMA_FILE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load canonical schema
    # --------------------------------------------------------

    with open(
        SCHEMA_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        schema_data = json.load(file)

    canonical_fields = schema_data["schema"]["canonical_fields"]

    aliases = schema_data["aliases"]

    # --------------------------------------------------------
    # Read ONLY the header first
    #
    # We don't need the complete 14,061-row dataset for
    # schema inspection.
    # --------------------------------------------------------

    source_columns = pd.read_csv(
        INPUT_FILE,
        nrows=0,
        low_memory=False
    ).columns.tolist()

    print(
        f"\nSource columns found: {len(source_columns)}"
    )

    # --------------------------------------------------------
    # Create normalized lookup
    # --------------------------------------------------------

    normalized_to_original = {}

    for column in source_columns:

        normalized_column = normalize_column(column)

        if normalized_column not in normalized_to_original:

            normalized_to_original[normalized_column] = []

        normalized_to_original[
            normalized_column
        ].append(column)

    # ========================================================
    # 5. MAP CANONICAL FIELDS TO SOURCE COLUMNS
    # ========================================================

    canonical_mapping_rows = []

    mapped_source_columns = set()

    for (
        canonical_name,
        data_type,
        category,
        required,
        description
    ) in canonical_fields:

        matched_columns = []

        candidate_aliases = aliases.get(
            canonical_name,
            [canonical_name]
        )

        for candidate in candidate_aliases:

            normalized_candidate = normalize_column(
                candidate
            )

            matches = normalized_to_original.get(
                normalized_candidate,
                []
            )

            matched_columns.extend(matches)

        # Remove duplicates while preserving order

        matched_columns = list(
            dict.fromkeys(matched_columns)
        )

        # Track source columns already mapped

        mapped_source_columns.update(
            matched_columns
        )

        if matched_columns:

            mapping_status = "MAPPED"

            primary_source_column = matched_columns[0]

        else:

            mapping_status = "NOT_FOUND"

            primary_source_column = ""

        canonical_mapping_rows.append({

            "canonical_field": canonical_name,

            "data_type": data_type,

            "category": category,

            "required_for_master": required,

            "description": description,

            "matched_source_columns":
                " | ".join(matched_columns),

            "primary_source_column":
                primary_source_column,

            "mapping_status":
                mapping_status

        })

    canonical_mapping_df = pd.DataFrame(
        canonical_mapping_rows
    )

    # ========================================================
    # 6. MAP EVERY SOURCE COLUMN
    # ========================================================

    reverse_mapping = {}

    for _, row in canonical_mapping_df.iterrows():

        matched_columns = row[
            "matched_source_columns"
        ]

        if not matched_columns:
            continue

        for source_column in matched_columns.split(" | "):

            reverse_mapping[
                source_column
            ] = row["canonical_field"]

    source_mapping_rows = []

    for source_column in source_columns:

        # ----------------------------------------------------
        # Direct canonical mapping
        # ----------------------------------------------------

        if source_column in reverse_mapping:

            source_mapping_rows.append({

                "source_column":
                    source_column,

                "normalized_source_column":
                    normalize_column(source_column),

                "canonical_field":
                    reverse_mapping[source_column],

                "classification":
                    "CANONICAL",

                "decision":
                    "KEEP_AND_STANDARDIZE",

                "notes":
                    "Mapped to canonical property schema."

            })

            continue

        # ----------------------------------------------------
        # Unmapped source column
        # ----------------------------------------------------

        classification, notes = (
            classify_unmapped_column(
                source_column
            )
        )

        decision_map = {

            "SOURCE_METADATA":
                "REVIEW_KEEP",

            "DERIVED_OR_ANALYTICAL":
                "REVIEW_DERIVED",

            "ALTERNATE_REPRESENTATION":
                "REVIEW_ALTERNATE",

            "UNMAPPED_REVIEW":
                "MANUAL_REVIEW"

        }

        source_mapping_rows.append({

            "source_column":
                source_column,

            "normalized_source_column":
                normalize_column(source_column),

            "canonical_field":
                "",

            "classification":
                classification,

            "decision":
                decision_map[classification],

            "notes":
                notes

        })

    source_mapping_df = pd.DataFrame(
        source_mapping_rows
    )

    # ========================================================
    # 7. CHECK REQUIRED CANONICAL FIELDS
    # ========================================================

    required_fields_df = canonical_mapping_df[
        canonical_mapping_df[
            "required_for_master"
        ] == "required"
    ]

    required_fields_not_found = (
        required_fields_df[
            required_fields_df[
                "mapping_status"
            ] == "NOT_FOUND"
        ]["canonical_field"]
        .tolist()
    )

    # ========================================================
    # 8. CREATE SUMMARY
    # ========================================================

    classification_counts = (
        source_mapping_df[
            "classification"
        ]
        .value_counts()
        .to_dict()
    )

    summary = {

        "input_file":
            str(INPUT_FILE),

        "source_column_count":
            len(source_columns),

        "canonical_field_count":
            len(canonical_fields),

        "canonical_fields_mapped":
            int(
                (
                    canonical_mapping_df[
                        "mapping_status"
                    ] == "MAPPED"
                ).sum()
            ),

        "canonical_fields_not_found":
            int(
                (
                    canonical_mapping_df[
                        "mapping_status"
                    ] == "NOT_FOUND"
                ).sum()
            ),

        "required_fields_not_found":
            required_fields_not_found,

        "source_columns_mapped":
            int(
                source_mapping_df[
                    "classification"
                ]
                .eq("CANONICAL")
                .sum()
            ),

        "source_columns_needing_review":
            int(
                source_mapping_df[
                    "classification"
                ]
                .ne("CANONICAL")
                .sum()
            ),

        "source_classification_counts":
            classification_counts,

        "note":
            (
                "Schema audit only. "
                "No cleaning, imputation, "
                "deduplication, value standardization "
                "or source modification is performed."
            )
    }

    # ========================================================
    # 9. SAVE RESULTS
    # ========================================================

    canonical_mapping_file = (
        OUTPUT_DIR /
        "canonical_field_mapping.csv"
    )

    source_mapping_file = (
        OUTPUT_DIR /
        "source_column_mapping.csv"
    )

    summary_file = (
        OUTPUT_DIR /
        "schema_summary.json"
    )

    canonical_mapping_df.to_csv(
        canonical_mapping_file,
        index=False
    )

    source_mapping_df.to_csv(
        source_mapping_file,
        index=False
    )

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # 10. PRINT SUMMARY
    # ========================================================

    print("\n" + "-" * 70)

    print(
        f"Source columns                : "
        f"{len(source_columns)}"
    )

    print(
        f"Canonical fields              : "
        f"{len(canonical_fields)}"
    )

    print(
        f"Canonical fields mapped       : "
        f"{summary['canonical_fields_mapped']}"
    )

    print(
        f"Canonical fields not found    : "
        f"{summary['canonical_fields_not_found']}"
    )

    print(
        f"Required fields not found     : "
        f"{len(required_fields_not_found)}"
    )

    print(
        f"Source columns mapped         : "
        f"{summary['source_columns_mapped']}"
    )

    print(
        f"Source columns needing review : "
        f"{summary['source_columns_needing_review']}"
    )

    # ========================================================
    # 11. REQUIRED FIELDS REQUIRING REVIEW
    # ========================================================

    if required_fields_not_found:

        print(
            "\nRequired fields needing review:"
        )

        for field in required_fields_not_found:

            print(
                f"  - {field}"
            )

    # ========================================================
    # 12. CLASSIFICATION SUMMARY
    # ========================================================

    print("\nSource column classification:")

    for category, count in (
        classification_counts.items()
    ):

        print(
            f"  {category:<30} {count}"
        )

    # ========================================================
    # 13. OUTPUT FILES
    # ========================================================

    print("\nGenerated files:")

    print(
        f"  {canonical_mapping_file}"
    )

    print(
        f"  {source_mapping_file}"
    )

    print(
        f"  {summary_file}"
    )

    print(
        "\nNo source data was modified."
    )

    print("=" * 70)


# ============================================================
# 14. PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()