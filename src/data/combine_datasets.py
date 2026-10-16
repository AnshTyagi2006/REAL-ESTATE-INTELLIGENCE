from pathlib import Path
import pandas as pd
import json


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "data" / "combined"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "real_estate_combined_raw.csv"
OUTPUT_REPORT = OUTPUT_DIR / "combination_report.json"


# ============================================================
# CITY DATASETS
# ============================================================

CITY_FILES = {
    "Bangalore": PROJECT_ROOT / "data" / "cities" / "bangalore" /
                 "bangalore_99acres_final_model_dataset.csv",

    "Chandigarh": PROJECT_ROOT / "data" / "cities" / "chandigarh" /
                  "chandigarh_99acres_final_model_dataset_v2.csv",

    "Dehradun": PROJECT_ROOT / "data" / "cities" / "dehradun" /
                "dehradun_99acres_final_model_dataset_v2.csv",

    "Delhi": PROJECT_ROOT / "data" / "cities" / "delhi" /
             "delhi_99acres_final_model_dataset_v2.csv",

    "Faridabad": PROJECT_ROOT / "data" / "cities" / "faridabad" /
                 "faridabad_99acres_final_model_dataset_v2.csv",

    "Ghaziabad": PROJECT_ROOT / "data" / "cities" / "gaziabad" /
                 "ghaziabad_99acres_final_model_dataset_v2.csv",

    "Greater Noida": PROJECT_ROOT / "data" / "cities" / "greater_noida" /
                     "greater_noida_99acres_final_model_dataset_v2.csv",

    "Gurgaon": PROJECT_ROOT / "data" / "cities" / "gurgaon" /
               "gurgaon_99acres_final_model_dataset.csv",

    "Hyderabad": PROJECT_ROOT / "data" / "cities" / "hyderabad" /
                 "hyderabad_99acres_final_model_dataset.csv",

    "Kolkata": PROJECT_ROOT / "data" / "cities" / "kolkata" /
               "kolkata_99acres_final_model_dataset (1).csv",

    "Mohali": PROJECT_ROOT / "data" / "cities" / "mohali" /
              "mohali_99acres_final_model_dataset_v2.csv",

    "Mumbai": PROJECT_ROOT / "data" / "cities" / "mumbai" /
              "mumbai_99acres_final_model_dataset.csv",

    "Noida": PROJECT_ROOT / "data" / "cities" / "noida" /
             "noida_99acres_final_model_dataset_v2.csv",

    "Panchkula": PROJECT_ROOT / "data" / "cities" / "panchkula" /
                 "panchkula_99acres_final_model_dataset_v2.csv",
}


# ============================================================
# READ DATASETS
# ============================================================

dataframes = []
city_statistics = []
schemas = {}

print("=" * 70)
print("REAL ESTATE DATASET COMBINATION")
print("=" * 70)

for city, file_path in CITY_FILES.items():

    print(f"\nReading: {city}")

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found for {city}:\n{file_path}"
        )

    df = pd.read_csv(file_path)

    # Add source metadata only.
    # No cleaning or transformation is performed.
    df["source_city"] = city
    df["source_file"] = file_path.name

    dataframes.append(df)

    schemas[city] = list(df.columns)

    city_statistics.append({
        "city": city,
        "file": file_path.name,
        "rows": len(df),
        "columns": len(df.columns),
    })

    print(f"  Rows    : {len(df):,}")
    print(f"  Columns : {len(df.columns)}")


# ============================================================
# SCHEMA ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("SCHEMA ANALYSIS")
print("=" * 70)

all_columns = set()

for columns in schemas.values():
    all_columns.update(columns)

common_columns = set.intersection(
    *(set(columns) for columns in schemas.values())
)

print(f"\nTotal unique columns across datasets : {len(all_columns)}")
print(f"Columns common to all datasets       : {len(common_columns)}")

schema_differences = {}

for city, columns in schemas.items():

    columns_set = set(columns)

    missing_from_city = sorted(all_columns - columns_set)

    extra_columns = sorted(columns_set - common_columns)

    schema_differences[city] = {
        "column_count": len(columns),
        "missing_columns": missing_from_city,
        "city_specific_columns": extra_columns,
    }


# ============================================================
# COMBINE DATASETS
# ============================================================

print("\n" + "=" * 70)
print("COMBINING DATASETS")
print("=" * 70)

combined_df = pd.concat(
    dataframes,
    ignore_index=True,
    sort=False
)


# ============================================================
# BASIC SOURCE VALIDATION
# ============================================================

expected_rows = sum(
    stat["rows"]
    for stat in city_statistics
)

actual_rows = len(combined_df)

if expected_rows != actual_rows:
    raise RuntimeError(
        f"Row-count mismatch!\n"
        f"Expected: {expected_rows}\n"
        f"Actual:   {actual_rows}"
    )


# ============================================================
# SAVE COMBINED DATASET
# ============================================================

combined_df.to_csv(
    OUTPUT_CSV,
    index=False
)


# ============================================================
# CREATE COMBINATION REPORT
# ============================================================

report = {
    "dataset_name": "Real Estate Combined Raw Dataset",

    "purpose": (
        "Combination of the city-level 99acres final datasets. "
        "No analytical cleaning, outlier removal, imputation, "
        "standardization, encoding, or feature engineering is "
        "performed in this script."
    ),

    "input_dataset_count": len(CITY_FILES),

    "input_datasets": city_statistics,

    "total_input_rows": expected_rows,

    "combined_rows": actual_rows,

    "total_columns": len(combined_df.columns),

    "combined_columns": list(combined_df.columns),

    "common_columns": sorted(common_columns),

    "all_columns": sorted(all_columns),

    "schema_differences": schema_differences,

    "source_city_distribution": (
        combined_df["source_city"]
        .value_counts()
        .sort_index()
        .to_dict()
    ),

    "source_file_distribution": (
        combined_df["source_file"]
        .value_counts()
        .to_dict()
    ),

    "processing": {
        "rows_removed": 0,
        "duplicates_removed": 0,
        "missing_values_filled": 0,
        "outliers_removed": 0,
        "categorical_values_standardized": False,
        "feature_engineering_performed": False,
    }
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
        ensure_ascii=False
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("COMBINATION COMPLETE")
print("=" * 70)

print(f"\nInput datasets : {len(CITY_FILES)}")
print(f"Input rows     : {expected_rows:,}")
print(f"Combined rows  : {actual_rows:,}")
print(f"Columns        : {len(combined_df.columns):,}")

print("\nCity-wise rows:")

for city, count in (
    combined_df["source_city"]
    .value_counts()
    .sort_index()
    .items()
):
    print(f"  {city:<20} {count:>6,}")

print("\nOutput files:")

print(f"CSV    : {OUTPUT_CSV}")
print(f"Report : {OUTPUT_REPORT}")

print("\nNo analytical cleaning was performed.")
print("This dataset is now the combined raw/master source.")
