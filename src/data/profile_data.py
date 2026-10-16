from pathlib import Path
import pandas as pd
import numpy as np
import json


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "combined"
    / "real_estate_combined_raw.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "profiling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


OUTPUT_REPORT = OUTPUT_DIR / "data_profile_report.json"
OUTPUT_MISSING = OUTPUT_DIR / "missing_values.csv"
OUTPUT_NUMERICAL = OUTPUT_DIR / "numerical_summary.csv"
OUTPUT_CATEGORICAL = OUTPUT_DIR / "categorical_summary.csv"
OUTPUT_DUPLICATES = OUTPUT_DIR / "duplicate_summary.csv"


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("REAL ESTATE DATA PROFILING")
print("=" * 70)

print(f"\nInput file:")
print(INPUT_FILE)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"\nCombined dataset not found:\n{INPUT_FILE}"
    )

df = pd.read_csv(INPUT_FILE)

print("\nDataset loaded successfully.")

print(f"Rows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")


# ============================================================
# BASIC DATASET INFORMATION
# ============================================================

print("\n" + "=" * 70)
print("BASIC DATASET INFORMATION")
print("=" * 70)

memory_mb = df.memory_usage(deep=True).sum() / (1024 ** 2)

basic_info = {
    "rows": int(len(df)),
    "columns": int(len(df.columns)),
    "memory_usage_mb": round(memory_mb, 2),
}


# ============================================================
# COLUMN / DATA TYPE PROFILE
# ============================================================

column_profile = []

for column in df.columns:

    series = df[column]

    column_profile.append({
        "column": column,
        "dtype": str(series.dtype),
        "non_null_count": int(series.notna().sum()),
        "missing_count": int(series.isna().sum()),
        "missing_percent": round(
            series.isna().mean() * 100,
            2
        ),
        "unique_count": int(series.nunique(dropna=True)),
    })


column_profile_df = pd.DataFrame(column_profile)


# ============================================================
# MISSING VALUE ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("MISSING VALUE ANALYSIS")
print("=" * 70)

missing_df = column_profile_df[
    [
        "column",
        "dtype",
        "missing_count",
        "missing_percent",
        "unique_count",
    ]
].copy()

missing_df = missing_df.sort_values(
    "missing_percent",
    ascending=False
)

missing_df.to_csv(
    OUTPUT_MISSING,
    index=False
)

print("\nTop columns by missing percentage:")

print(
    missing_df[
        ["column", "missing_count", "missing_percent"]
    ]
    .head(20)
    .to_string(index=False)
)


# ============================================================
# NUMERICAL PROFILE
# ============================================================

print("\n" + "=" * 70)
print("NUMERICAL PROFILE")
print("=" * 70)

numeric_columns = df.select_dtypes(
    include=np.number
).columns.tolist()

print(f"\nNumerical columns found: {len(numeric_columns)}")

if numeric_columns:

    numerical_summary = (
        df[numeric_columns]
        .describe()
        .T
        .reset_index()
        .rename(columns={"index": "column"})
    )

    numerical_summary["missing_count"] = [
        int(df[column].isna().sum())
        for column in numerical_summary["column"]
    ]

    numerical_summary["unique_count"] = [
        int(df[column].nunique(dropna=True))
        for column in numerical_summary["column"]
    ]

    numerical_summary.to_csv(
        OUTPUT_NUMERICAL,
        index=False
    )

    print(
        numerical_summary[
            [
                "column",
                "count",
                "mean",
                "min",
                "50%",
                "max",
            ]
        ].to_string(index=False)
    )

else:

    numerical_summary = pd.DataFrame()


# ============================================================
# CATEGORICAL PROFILE
# ============================================================

print("\n" + "=" * 70)
print("CATEGORICAL PROFILE")
print("=" * 70)

categorical_columns = df.select_dtypes(
    include=["object", "category", "bool"]
).columns.tolist()

print(
    f"\nCategorical/object columns found: "
    f"{len(categorical_columns)}"
)

categorical_records = []

for column in categorical_columns:

    series = df[column]

    value_counts = (
        series
        .fillna("<MISSING>")
        .astype(str)
        .value_counts(dropna=False)
    )

    for value, count in value_counts.items():

        categorical_records.append({
            "column": column,
            "value": value,
            "count": int(count),
            "percentage": round(
                count / len(df) * 100,
                2
            ),
        })


categorical_summary = pd.DataFrame(
    categorical_records
)

categorical_summary.to_csv(
    OUTPUT_CATEGORICAL,
    index=False
)


# ============================================================
# CITY PROFILE
# ============================================================

print("\n" + "=" * 70)
print("CITY PROFILE")
print("=" * 70)

if "source_city" in df.columns:

    city_counts = (
        df["source_city"]
        .value_counts()
        .sort_index()
    )

    print("\nListings by source city:\n")

    for city, count in city_counts.items():

        print(
            f"{city:<20} "
            f"{count:>6,}"
        )

else:

    city_counts = pd.Series(dtype=int)

    print(
        "\nWARNING: source_city column "
        "was not found."
    )


# ============================================================
# DUPLICATE ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("DUPLICATE ANALYSIS")
print("=" * 70)

duplicate_records = []


# ------------------------------------------------------------
# Exact duplicate rows
# ------------------------------------------------------------

exact_duplicate_count = int(
    df.duplicated(keep=False).sum()
)

exact_duplicate_groups = int(
    df.duplicated(keep=False).sum()
)


duplicate_records.append({
    "duplicate_type": "exact_duplicate_rows",
    "column_basis": "all_columns",
    "count": exact_duplicate_count,
})


# ------------------------------------------------------------
# Listing ID duplicates
# ------------------------------------------------------------

if "listing_id" in df.columns:

    listing_id_duplicate_rows = int(
        df["listing_id"].duplicated(keep=False).sum()
    )

    listing_id_duplicate_ids = int(
        df.loc[
            df["listing_id"].duplicated(keep=False),
            "listing_id"
        ].nunique()
    )

    duplicate_records.extend([
        {
            "duplicate_type": "duplicate_listing_rows",
            "column_basis": "listing_id",
            "count": listing_id_duplicate_rows,
        },
        {
            "duplicate_type": "duplicate_listing_ids",
            "column_basis": "listing_id",
            "count": listing_id_duplicate_ids,
        },
    ])

else:

    listing_id_duplicate_rows = None
    listing_id_duplicate_ids = None


# ------------------------------------------------------------
# URL duplicates
# ------------------------------------------------------------

if "listing_url" in df.columns:

    url_series = df["listing_url"].dropna()

    duplicate_url_rows = int(
        url_series.duplicated(keep=False).sum()
    )

    duplicate_url_values = int(
        url_series[
            url_series.duplicated(keep=False)
        ].nunique()
    )

    duplicate_records.extend([
        {
            "duplicate_type": "duplicate_url_rows",
            "column_basis": "listing_url",
            "count": duplicate_url_rows,
        },
        {
            "duplicate_type": "duplicate_urls",
            "column_basis": "listing_url",
            "count": duplicate_url_values,
        },
    ])


duplicate_summary = pd.DataFrame(
    duplicate_records
)

duplicate_summary.to_csv(
    OUTPUT_DUPLICATES,
    index=False
)

print(
    duplicate_summary.to_string(index=False)
)


# ============================================================
# IMPORTANT REAL-ESTATE FIELD CHECKS
# ============================================================

print("\n" + "=" * 70)
print("REAL ESTATE FIELD CHECKS")
print("=" * 70)

field_checks = {}


def numeric_field_check(column):

    if column not in df.columns:
        return None

    series = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    return {
        "present": True,
        "missing": int(series.isna().sum()),
        "zero": int((series == 0).sum()),
        "negative": int((series < 0).sum()),
        "positive": int((series > 0).sum()),
    }


important_numeric_fields = [
    "price_inr",
    "price_min_inr",
    "price_max_inr",
    "price_per_sqft",
    "area_sqft",
    "area_sqft_model",
    "area_min_sqft",
    "area_max_sqft",
    "bedrooms",
    "bathrooms",
    "balconies",
    "latitude",
    "longitude",
    "total_floors",
]


for field in important_numeric_fields:

    field_checks[field] = numeric_field_check(
        field
    )


# ============================================================
# COORDINATE VALIDATION PROFILE
# ============================================================

if (
    "latitude" in df.columns
    and "longitude" in df.columns
):

    latitude = pd.to_numeric(
        df["latitude"],
        errors="coerce"
    )

    longitude = pd.to_numeric(
        df["longitude"],
        errors="coerce"
    )

    invalid_latitude = int(
        (
            latitude.notna()
            & ~latitude.between(-90, 90)
        ).sum()
    )

    invalid_longitude = int(
        (
            longitude.notna()
            & ~longitude.between(-180, 180)
        ).sum()
    )

    zero_coordinates = int(
        (
            (latitude == 0)
            & (longitude == 0)
        ).sum()
    )

else:

    invalid_latitude = None
    invalid_longitude = None
    zero_coordinates = None


field_checks["coordinates"] = {
    "invalid_latitude": invalid_latitude,
    "invalid_longitude": invalid_longitude,
    "zero_zero_coordinates": zero_coordinates,
}


# ============================================================
# PROFILE REPORT
# ============================================================

report = {
    "dataset": {
        "file": str(INPUT_FILE),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "memory_usage_mb": round(memory_mb, 2),
    },

    "city_distribution": {
        str(city): int(count)
        for city, count in city_counts.items()
    },

    "column_profile": column_profile,

    "numerical_columns": numeric_columns,

    "categorical_columns": categorical_columns,

    "duplicate_analysis": {
        "exact_duplicate_rows": exact_duplicate_count,
        "duplicate_listing_rows": listing_id_duplicate_rows,
        "duplicate_listing_ids": listing_id_duplicate_ids,
    },

    "important_field_checks": field_checks,

    "coordinate_checks": {
        "invalid_latitude": invalid_latitude,
        "invalid_longitude": invalid_longitude,
        "zero_zero_coordinates": zero_coordinates,
    },

    "profiling_only": True,

    "data_modified": False,

    "cleaning_performed": False,

    "standardization_performed": False,

    "feature_engineering_performed": False,
}


with open(
    OUTPUT_REPORT,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        report,
        file,
        indent=4,
        ensure_ascii=False,
        default=str
    )


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n" + "=" * 70)
print("DATA PROFILING COMPLETE")
print("=" * 70)

print(f"\nRows    : {len(df):,}")
print(f"Columns : {len(df.columns):,}")

print(
    f"\nExact duplicate rows: "
    f"{exact_duplicate_count:,}"
)

if listing_id_duplicate_ids is not None:

    print(
        f"Duplicate listing IDs: "
        f"{listing_id_duplicate_ids:,}"
    )

print("\nGenerated files:")

print(
    f"Profile report     : {OUTPUT_REPORT}"
)

print(
    f"Missing values     : {OUTPUT_MISSING}"
)

print(
    f"Numerical summary  : {OUTPUT_NUMERICAL}"
)

print(
    f"Categorical summary : {OUTPUT_CATEGORICAL}"
)

print(
    f"Duplicate summary  : {OUTPUT_DUPLICATES}"
)

print("\nIMPORTANT:")
print("The source dataset has NOT been modified.")
print("No cleaning or preprocessing was performed.")