from __future__ import annotations

import re
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
    / "master"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "real_estate_master_v1.csv"
)


def clean_text(value):
    """Clean simple text without changing its meaning."""

    if pd.isna(value):
        return pd.NA

    value = str(value).strip()

    if value == "":
        return pd.NA

    return value


def clean_text_columns(df):

    text_columns = [
        "listing_id",
        "source",
        "listing_url",
        "property_name",
        "record_type",
        "city",
        "locality",
        "society",
        "property_type",
        "product_type",
        "configuration",
        "furnishing",
        "status",
        "listing_category",
        "listing_type",
        "seller_type",
        "seller_class",
        "rera_registered",
        "rera_id",
        "area_basis",
        "parking",
        "reserved_parking",
        "amenities",
        "features",
        "facing",
        "overlooking",
        "builder",
        "builder_name",
        "seller_name",
        "seller_company",
        "seller_agent",
        "description",
        "posted_date",
        "updated_date",
        "scraped_at",
        "source_city",
        "source_file",
        "posted_at",
        "updated_at",
        "posted_by",
        "quality_flags",
    ]

    for column in text_columns:

        if column in df.columns:

            df[column] = df[column].apply(
                clean_text
            )

    return df


def convert_numeric_columns(df):

    numeric_columns = [
        "bedrooms",
        "bathrooms",
        "balconies",
        "floor",
        "total_floors",
        "property_age_years",
        "area_sqft",
        "area_min_sqft",
        "area_max_sqft",
        "carpet_area_sqft",
        "builtup_area_sqft",
        "superbuiltup_area_sqft",
        "price_inr",
        "price_min_inr",
        "price_max_inr",
        "price_per_sqft",
        "parking_count",
        "amenities_count",
        "features_count",
        "nearby_landmarks_count",
        "latitude",
        "longitude",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    return df


def extract_bedrooms_from_configuration(df):

    if "configuration" not in df.columns:
        return df

    if "bedrooms" not in df.columns:
        df["bedrooms"] = pd.NA

    pattern = r"(\d+)\s*BHK"

    extracted = (
        df["configuration"]
        .astype("string")
        .str.extract(
            pattern,
            flags=re.IGNORECASE,
            expand=False
        )
    )

    extracted = pd.to_numeric(
        extracted,
        errors="coerce"
    )

    missing_bedrooms = (
        df["bedrooms"].isna()
        & extracted.notna()
    )

    df.loc[
        missing_bedrooms,
        "bedrooms"
    ] = extracted[missing_bedrooms]

    return df


def standardize_furnishing(df):

    if "furnishing" not in df.columns:
        return df

    mapping = {
        "Furnished": "Furnished",
        "furnished": "Furnished",

        "Unfurnished": "Unfurnished",
        "unfurnished": "Unfurnished",

        "Semifurnished": "Semi-Furnished",
        "Semi Furnished": "Semi-Furnished",
        "semi furnished": "Semi-Furnished",
    }

    df["furnishing"] = (
        df["furnishing"]
        .replace(mapping)
    )

    return df


def create_property_id(df):

    df.insert(
        0,
        "property_id",
        [
            f"RE-{i:08d}"
            for i in range(
                1,
                len(df) + 1
            )
        ]
    )

    return df


def create_derived_features(df):

    # Price in lakh
    if "price_inr" in df.columns:

        df["price_lakh"] = (
            df["price_inr"] / 100_000
        )

    # Price in crore
    if "price_inr" in df.columns:

        df["price_crore"] = (
            df["price_inr"] / 10_000_000
        )

    # Floor ratio
    if (
        "floor" in df.columns
        and "total_floors" in df.columns
    ):

        df["floor_ratio"] = (
            df["floor"]
            / df["total_floors"].replace(
                0,
                pd.NA
            )
        )

    # Log price
    if "price_inr" in df.columns:

        df["log_price"] = (
            df["price_inr"]
            .where(
                df["price_inr"] > 0
            )
        )

        df["log_price"] = (
            df["log_price"]
            .apply(
                lambda x:
                __import__("math").log1p(x)
                if pd.notna(x)
                else pd.NA
            )
        )

    # Log price per sqft
    if "price_per_sqft" in df.columns:

        df["log_price_per_sqft"] = (
            df["price_per_sqft"]
            .where(
                df["price_per_sqft"] > 0
            )
        )

        df["log_price_per_sqft"] = (
            df["log_price_per_sqft"]
            .apply(
                lambda x:
                __import__("math").log1p(x)
                if pd.notna(x)
                else pd.NA
            )
        )

    return df


def main():

    print("\n" + "=" * 75)
    print("REAL ESTATE INTELLIGENCE PLATFORM")
    print("STANDARDIZATION PIPELINE — V1")
    print("=" * 75)

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"\nInput file not found:\n{INPUT_FILE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nReading raw combined dataset...")

    df = pd.read_csv(
        INPUT_FILE,
        low_memory=False
    )

    original_rows = len(df)

    print(
        f"Original rows    : {original_rows:,}"
    )

    print(
        f"Original columns : {len(df.columns)}"
    )

    # ---------------------------------------------------------
    # 1. Clean text
    # ---------------------------------------------------------

    df = clean_text_columns(df)

    print("\n[1/6] Text fields cleaned.")

    # ---------------------------------------------------------
    # 2. Numeric conversion
    # ---------------------------------------------------------

    df = convert_numeric_columns(df)

    print("[2/6] Numeric fields standardized.")

    # ---------------------------------------------------------
    # 3. Recover BHK from configuration
    # ---------------------------------------------------------

    bedrooms_before = (
        df["bedrooms"].notna().sum()
        if "bedrooms" in df.columns
        else 0
    )

    df = extract_bedrooms_from_configuration(df)

    bedrooms_after = (
        df["bedrooms"].notna().sum()
        if "bedrooms" in df.columns
        else 0
    )

    print("[3/6] Bedroom values checked.")

    print(
        f"    Bedrooms before : {bedrooms_before:,}"
    )

    print(
        f"    Bedrooms after  : {bedrooms_after:,}"
    )

    print(
        f"    Recovered       : "
        f"{bedrooms_after - bedrooms_before:,}"
    )

    # ---------------------------------------------------------
    # 4. Furnishing
    # ---------------------------------------------------------

    df = standardize_furnishing(df)

    print("[4/6] Readable furnishing values standardized.")

    # ---------------------------------------------------------
    # 5. Create internal ID
    # ---------------------------------------------------------

    df = create_property_id(df)

    print("[5/6] Internal property IDs created.")

    # ---------------------------------------------------------
    # 6. Derived fields
    # ---------------------------------------------------------

    df = create_derived_features(df)

    print("[6/6] Derived numerical fields created.")

    # ---------------------------------------------------------
    # Validate row count
    # ---------------------------------------------------------

    final_rows = len(df)

    if final_rows != original_rows:

        raise RuntimeError(
            "\nRow count changed during standardization."
        )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n" + "-" * 75)

    print(
        f"Final rows       : {final_rows:,}"
    )

    print(
        f"Final columns    : {len(df.columns)}"
    )

    print(
        f"Output file      :\n{OUTPUT_FILE}"
    )

    print(
        "\nImportant:"
    )

    print(
        "Original raw dataset was NOT modified."
    )

    print(
        "Coded values such as facing, parking and "
        "listing_type were NOT guessed."
    )

    print("=" * 75)


if __name__ == "__main__":
    main()