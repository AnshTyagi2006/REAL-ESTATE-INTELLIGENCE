from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd


warnings.filterwarnings("ignore")


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "modeling"
    / "valuation_modeling_dataset.csv"
)

MODEL_PATH = (
    PROJECT_ROOT
    / "data"
    / "models"
    / "lightgbm_tuned"
    / "lightgbm_tuned_model.joblib"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "valuation"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONFIGURATION
# ============================================================

RANDOM_SAMPLE_SIZE = None
# None = validate every eligible property.
# Example: 500 = validate only 500 random properties.

RANDOM_STATE = 42

MIN_COMPARABLES_FOR_DIRECT_USE = 5

MAX_TIER_1_COMPARABLES = 20
MAX_TIER_2_COMPARABLES = 20
MAX_TIER_3_COMPARABLES = 20

AREA_TOLERANCE = 0.20
BEDROOM_TOLERANCE = 1
BATHROOM_TOLERANCE = 1

TIER_1_MAX_DISTANCE_KM = 5.0
TIER_2_MAX_DISTANCE_KM = 5.0
TIER_3_MAX_DISTANCE_KM = 15.0


# Current Hybrid V1 weights
COMPARABLE_WEIGHT = 0.45
LOCALITY_WEIGHT = 0.35
ML_WEIGHT = 0.20


# ============================================================
# BASIC HELPERS
# ============================================================

def money(value):
    if pd.isna(value):
        return "NA"

    value = float(value)

    if value >= 10_000_000:
        return f"₹{value / 10_000_000:.2f}Cr"

    if value >= 100_000:
        return f"₹{value / 100_000:.2f}L"

    return f"₹{value:,.0f}"


def safe_float(value):
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance between two coordinates.
    """

    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    dlat = lat2 - lat1
    dlon = np.radians(lon2 - lon1)

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    )

    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def absolute_percentage_error(actual, predicted):
    if actual == 0 or pd.isna(actual) or pd.isna(predicted):
        return np.nan

    return abs(predicted - actual) / abs(actual) * 100


def signed_percentage_error(actual, predicted):
    if actual == 0 or pd.isna(actual) or pd.isna(predicted):
        return np.nan

    return (predicted - actual) / abs(actual) * 100


# ============================================================
# MODEL PREDICTION
# ============================================================

def predict_ml_values(model, dataframe):
    """
    Generate predictions from the saved tuned LightGBM model.

    The function supports both:
    1. a preprocessing Pipeline
    2. a native LightGBM model using pandas categorical columns
    """

    model_features = [
        "valuation_area_sqft",
        "city",
        "locality",
        "bedrooms",
        "bathrooms",
        "latitude",
        "longitude",
        "property_type",
        "floor",
        "total_floors",
    ]

    X = dataframe[model_features].copy()

    # --------------------------------------------------------
    # Case 1: Pipeline
    # --------------------------------------------------------

    if hasattr(model, "steps"):
        predictions_log = model.predict(X)

        return np.expm1(predictions_log)

    # --------------------------------------------------------
    # Case 2: Native LightGBM model
    # --------------------------------------------------------

    categorical_columns = [
        "city",
        "locality",
        "property_type",
    ]

    for column in categorical_columns:
        if column in X.columns:
            X[column] = X[column].astype("category")

    try:
        predictions_log = model.predict(X)
        return np.expm1(predictions_log)

    except Exception:
        # Reconstruct categorical categories from the original
        # modeling dataset if required by the saved LightGBM model.
        for column in categorical_columns:
            if column in X.columns:
                X[column] = X[column].astype(str).astype("category")

        predictions_log = model.predict(X)

        return np.expm1(predictions_log)


# ============================================================
# COMPARABLE ENGINE
# ============================================================

def get_comparable_valuation(target, candidates):
    """
    Calculate comparable-based valuation for one target property.

    Target's own row must already be removed from candidates.
    """

    target_city = target["city"]
    target_locality = target["locality"]
    target_area = safe_float(target["valuation_area_sqft"])
    target_bedrooms = safe_float(target["bedrooms"])
    target_bathrooms = safe_float(target["bathrooms"])
    target_lat = safe_float(target["latitude"])
    target_lon = safe_float(target["longitude"])
    target_property_type = target["property_type"]

    if pd.isna(target_area):
        return None

    city_candidates = candidates[
        candidates["city"] == target_city
    ].copy()

    if city_candidates.empty:
        return None

    # --------------------------------------------------------
    # Area filter
    # --------------------------------------------------------

    city_candidates = city_candidates[
        city_candidates["valuation_area_sqft"].between(
            target_area * (1 - AREA_TOLERANCE),
            target_area * (1 + AREA_TOLERANCE),
        )
    ].copy()

    if city_candidates.empty:
        return None

    # --------------------------------------------------------
    # Bedroom filter
    # --------------------------------------------------------

    if not pd.isna(target_bedrooms):

        city_candidates = city_candidates[
            (
                city_candidates["bedrooms"].isna()
            )
            |
            (
                abs(
                    city_candidates["bedrooms"]
                    - target_bedrooms
                )
                <= BEDROOM_TOLERANCE
            )
        ].copy()

    if city_candidates.empty:
        return None

    # --------------------------------------------------------
    # Bathroom filter
    # --------------------------------------------------------

    if not pd.isna(target_bathrooms):

        city_candidates = city_candidates[
            (
                city_candidates["bathrooms"].isna()
            )
            |
            (
                abs(
                    city_candidates["bathrooms"]
                    - target_bathrooms
                )
                <= BATHROOM_TOLERANCE
            )
        ].copy()

    if city_candidates.empty:
        return None

    # --------------------------------------------------------
    # Geographic distance
    # --------------------------------------------------------

    city_candidates["distance_km"] = haversine_km(
        target_lat,
        target_lon,
        city_candidates["latitude"].astype(float).values,
        city_candidates["longitude"].astype(float).values,
    )

    city_candidates["same_locality"] = (
        city_candidates["locality"]
        == target_locality
    )

    city_candidates["area_difference_pct"] = (
        abs(
            city_candidates["valuation_area_sqft"]
            - target_area
        )
        / target_area
        * 100
    )

    # --------------------------------------------------------
    # Geographic tiers
    # --------------------------------------------------------

    tier_1 = city_candidates[
        city_candidates["same_locality"]
        & (
            city_candidates["distance_km"]
            <= TIER_1_MAX_DISTANCE_KM
        )
    ].copy()

    tier_2 = city_candidates[
        (~city_candidates["same_locality"])
        & (
            city_candidates["distance_km"]
            <= TIER_2_MAX_DISTANCE_KM
        )
    ].copy()

    tier_3 = city_candidates[
        (
            city_candidates["distance_km"]
            > TIER_2_MAX_DISTANCE_KM
        )
        & (
            city_candidates["distance_km"]
            <= TIER_3_MAX_DISTANCE_KM
        )
    ].copy()

    # --------------------------------------------------------
    # Select geographic evidence
    #
    # Prefer Tier 1.
    # If insufficient, use Tier 2.
    # If still insufficient, use Tier 3.
    # --------------------------------------------------------

    if len(tier_1) >= MIN_COMPARABLES_FOR_DIRECT_USE:

        selected = tier_1.sort_values(
            ["distance_km", "area_difference_pct"]
        ).head(MAX_TIER_1_COMPARABLES).copy()

        evidence_tier = "Tier 1 - Same locality"

    elif len(tier_1) + len(tier_2) >= MIN_COMPARABLES_FOR_DIRECT_USE:

        selected = pd.concat(
            [tier_1, tier_2],
            ignore_index=True
        )

        selected = selected.sort_values(
            ["distance_km", "area_difference_pct"]
        ).head(MAX_TIER_2_COMPARABLES).copy()

        evidence_tier = "Tier 2 - Nearby locality"

    elif len(tier_1) + len(tier_2) + len(tier_3) >= MIN_COMPARABLES_FOR_DIRECT_USE:

        selected = pd.concat(
            [tier_1, tier_2, tier_3],
            ignore_index=True
        )

        selected = selected.sort_values(
            ["distance_km", "area_difference_pct"]
        ).head(MAX_TIER_3_COMPARABLES).copy()

        evidence_tier = "Tier 3 - Wider market fallback"

    else:
        return None

    # --------------------------------------------------------
    # Calculate comparable price per sqft
    # --------------------------------------------------------

    selected["price_per_sqft"] = (
        selected["asking_price_inr"]
        / selected["valuation_area_sqft"]
    )

    selected = selected.replace(
        [np.inf, -np.inf],
        np.nan
    )

    selected = selected.dropna(
        subset=["price_per_sqft"]
    )

    if len(selected) < MIN_COMPARABLES_FOR_DIRECT_USE:
        return None

    # --------------------------------------------------------
    # IQR outlier removal
    # --------------------------------------------------------

    q1 = selected["price_per_sqft"].quantile(0.25)
    q3 = selected["price_per_sqft"].quantile(0.75)

    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    selected["price_outlier"] = (
        (selected["price_per_sqft"] < lower_bound)
        |
        (selected["price_per_sqft"] > upper_bound)
    )

    usable = selected[
        ~selected["price_outlier"]
    ].copy()

    if len(usable) < 3:
        usable = selected.copy()

    # --------------------------------------------------------
    # Comparable central estimate
    # --------------------------------------------------------

    median_ppsf = usable[
        "price_per_sqft"
    ].median()

    comparable_value = (
        median_ppsf
        * target_area
    )

    return {
        "comparable_value": comparable_value,
        "comparable_ppsf": median_ppsf,
        "selected_comparable_count": len(selected),
        "usable_comparable_count": len(usable),
        "same_locality_count": int(
            selected["same_locality"].sum()
        ),
        "evidence_tier": evidence_tier,
        "distance_median_km": selected[
            "distance_km"
        ].median(),
        "distance_max_km": selected[
            "distance_km"
        ].max(),
    }


# ============================================================
# LOCALITY / BHK VALUATION
# ============================================================

def get_locality_valuation(target, candidates):
    """
    Calculate locality + BHK valuation.

    IMPORTANT:
    The target row is excluded before this function is called.
    """

    locality = target["locality"]
    city = target["city"]
    bedrooms = safe_float(target["bedrooms"])
    area = safe_float(target["valuation_area_sqft"])

    if pd.isna(area):
        return None

    locality_data = candidates[
        (candidates["city"] == city)
        &
        (candidates["locality"] == locality)
    ].copy()

    if locality_data.empty:
        return None

    locality_data["price_per_sqft"] = (
        locality_data["asking_price_inr"]
        / locality_data["valuation_area_sqft"]
    )

    locality_data = locality_data.replace(
        [np.inf, -np.inf],
        np.nan
    )

    locality_data = locality_data.dropna(
        subset=["price_per_sqft"]
    )

    if locality_data.empty:
        return None

    # --------------------------------------------------------
    # Prefer same-BHK properties
    # --------------------------------------------------------

    if not pd.isna(bedrooms):

        bhk_data = locality_data[
            locality_data["bedrooms"] == bedrooms
        ].copy()

    else:
        bhk_data = pd.DataFrame()

    if len(bhk_data) >= 3:

        analysis_data = bhk_data
        basis = "same_locality_same_bhk"

    else:

        analysis_data = locality_data
        basis = "same_locality_all_bhk"

    if analysis_data.empty:
        return None

    median_ppsf = analysis_data[
        "price_per_sqft"
    ].median()

    locality_value = (
        median_ppsf
        * area
    )

    return {
        "locality_value": locality_value,
        "locality_ppsf": median_ppsf,
        "locality_property_count": len(locality_data),
        "locality_bhk_property_count": len(bhk_data),
        "locality_basis": basis,
    }


# ============================================================
# EVIDENCE QUALITY
# ============================================================

def classify_evidence(comparable_result, locality_result):

    if comparable_result is None:
        return "WEAK"

    comparable_count = (
        comparable_result["usable_comparable_count"]
    )

    locality_count = 0

    if locality_result is not None:
        locality_count = (
            locality_result["locality_bhk_property_count"]
        )

    if (
        comparable_count >= 7
        and locality_count >= 5
        and comparable_result["evidence_tier"]
        == "Tier 1 - Same locality"
    ):
        return "STRONG"

    if (
        comparable_count >= 5
        and locality_count >= 3
    ):
        return "MODERATE"

    return "WEAK"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 80)
    print("HYBRID VALUATION BACKTEST")
    print("=" * 80)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    print("\nLoading modeling dataset...")

    df = pd.read_csv(MODEL_DATA_PATH)

    print(f"Total rows loaded: {len(df):,}")

    required_columns = [
        "property_id",
        "listing_id",
        "asking_price_inr",
        "valuation_area_sqft",
        "city",
        "locality",
        "bedrooms",
        "bathrooms",
        "latitude",
        "longitude",
        "property_type",
        "floor",
        "total_floors",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing_columns)
        )

    # --------------------------------------------------------
    # Prepare numeric fields
    # --------------------------------------------------------

    numeric_columns = [
        "asking_price_inr",
        "valuation_area_sqft",
        "bedrooms",
        "bathrooms",
        "latitude",
        "longitude",
        "floor",
        "total_floors",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # Eligible backtesting records
    # --------------------------------------------------------

    eligible = df[
        df["asking_price_inr"].notna()
        &
        (df["asking_price_inr"] > 0)
        &
        df["valuation_area_sqft"].notna()
        &
        (df["valuation_area_sqft"] > 0)
        &
        df["city"].notna()
        &
        df["locality"].notna()
        &
        df["bedrooms"].notna()
        &
        df["bathrooms"].notna()
        &
        df["latitude"].notna()
        &
        df["longitude"].notna()
    ].copy()

    print(
        f"Eligible properties for backtesting: "
        f"{len(eligible):,}"
    )

    # --------------------------------------------------------
    # Optional sampling
    # --------------------------------------------------------

    if RANDOM_SAMPLE_SIZE is not None:

        sample_size = min(
            RANDOM_SAMPLE_SIZE,
            len(eligible)
        )

        eligible = eligible.sample(
            n=sample_size,
            random_state=RANDOM_STATE
        ).copy()

        print(
            f"Using random validation sample: "
            f"{len(eligible):,}"
        )

    # --------------------------------------------------------
    # Load tuned LightGBM
    # --------------------------------------------------------

    print("\nLoading tuned LightGBM model...")

    model = joblib.load(MODEL_PATH)

    print("Model loaded successfully.")

    # --------------------------------------------------------
    # ML predictions
    #
    # We calculate these once for all records.
    # The target's asking price is never used by the model.
    # --------------------------------------------------------

    print("\nGenerating ML predictions...")

    eligible["ml_predicted_price"] = (
        predict_ml_values(
            model,
            eligible
        )
    )

    print("ML predictions generated.")

    # --------------------------------------------------------
    # Candidate dataset
    #
    # All asking prices belong to other listings.
    # For each target, the target itself is removed.
    # --------------------------------------------------------

    candidates = eligible.copy()

    results = []

    total = len(eligible)

    print("\nStarting backtesting...")
    print(f"Properties to evaluate: {total:,}")
    print("-" * 80)

    # --------------------------------------------------------
    # Main target loop
    # --------------------------------------------------------

    for counter, (target_index, target) in enumerate(
        eligible.iterrows(),
        start=1
    ):

        # Remove target itself.
        candidate_pool = candidates[
            candidates["property_id"]
            != target["property_id"]
        ].copy()

        comparable_result = (
            get_comparable_valuation(
                target,
                candidate_pool
            )
        )

        locality_result = (
            get_locality_valuation(
                target,
                candidate_pool
            )
        )

        # ----------------------------------------------------
        # Extract ML prediction
        # ----------------------------------------------------

        ml_value = safe_float(
            target["ml_predicted_price"]
        )

        # ----------------------------------------------------
        # Hybrid calculation
        # ----------------------------------------------------

        hybrid_value = np.nan

        if (
            comparable_result is not None
            and locality_result is not None
            and not pd.isna(ml_value)
        ):

            hybrid_value = (
                COMPARABLE_WEIGHT
                * comparable_result[
                    "comparable_value"
                ]
                +
                LOCALITY_WEIGHT
                * locality_result[
                    "locality_value"
                ]
                +
                ML_WEIGHT
                * ml_value
            )

        # ----------------------------------------------------
        # Individual method values
        # ----------------------------------------------------

        comparable_value = np.nan

        if comparable_result is not None:
            comparable_value = (
                comparable_result[
                    "comparable_value"
                ]
            )

        locality_value = np.nan

        if locality_result is not None:
            locality_value = (
                locality_result[
                    "locality_value"
                ]
            )

        actual_price = float(
            target["asking_price_inr"]
        )

        # ----------------------------------------------------
        # Errors
        # ----------------------------------------------------

        result = {
            "property_id": target["property_id"],
            "listing_id": target["listing_id"],
            "city": target["city"],
            "locality": target["locality"],
            "bedrooms": target["bedrooms"],
            "valuation_area_sqft": target[
                "valuation_area_sqft"
            ],
            "actual_asking_price": actual_price,

            "ml_value": ml_value,
            "comparable_value": comparable_value,
            "locality_value": locality_value,
            "hybrid_value": hybrid_value,

            "ml_abs_error_pct": (
                absolute_percentage_error(
                    actual_price,
                    ml_value
                )
            ),

            "comparable_abs_error_pct": (
                absolute_percentage_error(
                    actual_price,
                    comparable_value
                )
            ),

            "locality_abs_error_pct": (
                absolute_percentage_error(
                    actual_price,
                    locality_value
                )
            ),

            "hybrid_abs_error_pct": (
                absolute_percentage_error(
                    actual_price,
                    hybrid_value
                )
            ),

            "ml_signed_error_pct": (
                signed_percentage_error(
                    actual_price,
                    ml_value
                )
            ),

            "comparable_signed_error_pct": (
                signed_percentage_error(
                    actual_price,
                    comparable_value
                )
            ),

            "locality_signed_error_pct": (
                signed_percentage_error(
                    actual_price,
                    locality_value
                )
            ),

            "hybrid_signed_error_pct": (
                signed_percentage_error(
                    actual_price,
                    hybrid_value
                )
            ),
        }

        # ----------------------------------------------------
        # Comparable metadata
        # ----------------------------------------------------

        if comparable_result is not None:

            result.update(
                {
                    "comparable_count":
                        comparable_result[
                            "selected_comparable_count"
                        ],

                    "usable_comparable_count":
                        comparable_result[
                            "usable_comparable_count"
                        ],

                    "same_locality_count":
                        comparable_result[
                            "same_locality_count"
                        ],

                    "comparable_evidence_tier":
                        comparable_result[
                            "evidence_tier"
                        ],

                    "median_comparable_distance_km":
                        comparable_result[
                            "distance_median_km"
                        ],
                }
            )

        else:

            result.update(
                {
                    "comparable_count": 0,
                    "usable_comparable_count": 0,
                    "same_locality_count": 0,
                    "comparable_evidence_tier": "No evidence",
                    "median_comparable_distance_km": np.nan,
                }
            )

        # ----------------------------------------------------
        # Locality metadata
        # ----------------------------------------------------

        if locality_result is not None:

            result.update(
                {
                    "locality_property_count":
                        locality_result[
                            "locality_property_count"
                        ],

                    "locality_bhk_property_count":
                        locality_result[
                            "locality_bhk_property_count"
                        ],

                    "locality_basis":
                        locality_result[
                            "locality_basis"
                        ],
                }
            )

        else:

            result.update(
                {
                    "locality_property_count": 0,
                    "locality_bhk_property_count": 0,
                    "locality_basis": "No evidence",
                }
            )

        # ----------------------------------------------------
        # Evidence quality
        # ----------------------------------------------------

        result["evidence_quality"] = (
            classify_evidence(
                comparable_result,
                locality_result
            )
        )

        # ----------------------------------------------------
        # Hybrid range
        #
        # For validation we construct an evidence range from
        # comparable and locality signals.
        # This is NOT a statistical confidence interval.
        # ----------------------------------------------------

        evidence_values = [
            value
            for value in [
                comparable_value,
                locality_value,
                ml_value,
            ]
            if not pd.isna(value)
        ]

        if len(evidence_values) >= 2:

            result["evidence_low"] = min(
                evidence_values
            )

            result["evidence_high"] = max(
                evidence_values
            )

            result["actual_inside_evidence_range"] = (
                result["evidence_low"]
                <= actual_price
                <= result["evidence_high"]
            )

        else:

            result["evidence_low"] = np.nan
            result["evidence_high"] = np.nan
            result[
                "actual_inside_evidence_range"
            ] = False

        results.append(result)

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if counter % 100 == 0 or counter == total:

            print(
                f"Processed {counter:,}/{total:,}"
            )

    # ========================================================
    # RESULTS DATAFRAME
    # ========================================================

    results_df = pd.DataFrame(results)

    results_path = (
        OUTPUT_DIR
        / "hybrid_backtest_property_results.csv"
    )

    results_df.to_csv(
        results_path,
        index=False
    )

    print("\nProperty-level results saved:")
    print(results_path)

    # ========================================================
    # VALIDATION METRICS
    # ========================================================

    def calculate_metrics(
        dataframe,
        prediction_column
    ):

        valid = dataframe[
            dataframe[prediction_column].notna()
        ].copy()

        if valid.empty:
            return None

        actual = valid[
            "actual_asking_price"
        ]

        predicted = valid[
            prediction_column
        ]

        errors = predicted - actual

        abs_errors = abs(errors)

        abs_percentage_errors = (
            abs_errors
            / actual.abs()
            * 100
        )

        rmse = np.sqrt(
            np.mean(errors ** 2)
        )

        return {
            "n": int(len(valid)),
            "mae_inr": float(
                np.mean(abs_errors)
            ),
            "rmse_inr": float(rmse),
            "mean_absolute_pct": float(
                np.mean(abs_percentage_errors)
            ),
            "median_absolute_pct": float(
                np.median(abs_percentage_errors)
            ),
            "mean_prediction_error_inr": float(
                np.mean(errors)
            ),
            "median_prediction_error_inr": float(
                np.median(errors)
            ),
        }

    methods = {
        "ML Only": "ml_value",
        "Comparable Only": "comparable_value",
        "Locality Only": "locality_value",
        "Hybrid V1": "hybrid_value",
    }

    overall_metrics = {}

    print("\n")
    print("=" * 80)
    print("OVERALL BACKTEST RESULTS")
    print("=" * 80)

    for method_name, column in methods.items():

        metrics = calculate_metrics(
            results_df,
            column
        )

        overall_metrics[method_name] = metrics

        if metrics is None:
            print(
                f"\n{method_name}: No valid predictions"
            )
            continue

        print(f"\n{method_name}")
        print("-" * 40)
        print(
            f"N                    : {metrics['n']:,}"
        )
        print(
            f"MAE                  : {money(metrics['mae_inr'])}"
        )
        print(
            f"RMSE                 : {money(metrics['rmse_inr'])}"
        )
        print(
            f"Mean Absolute Error %: "
            f"{metrics['mean_absolute_pct']:.2f}%"
        )
        print(
            f"Median Absolute Error%: "
            f"{metrics['median_absolute_pct']:.2f}%"
        )
        print(
            f"Mean Prediction Error: "
            f"{money(metrics['mean_prediction_error_inr'])}"
        )

    # ========================================================
    # EVIDENCE COVERAGE
    # ========================================================

    hybrid_valid = results_df[
        results_df["hybrid_value"].notna()
    ].copy()

    coverage = {
        "total_eligible_properties": int(
            len(results_df)
        ),
        "hybrid_valid_predictions": int(
            len(hybrid_valid)
        ),
        "hybrid_coverage_pct": float(
            len(hybrid_valid)
            / len(results_df)
            * 100
        ),
        "strong_evidence_count": int(
            (
                results_df["evidence_quality"]
                == "STRONG"
            ).sum()
        ),
        "moderate_evidence_count": int(
            (
                results_df["evidence_quality"]
                == "MODERATE"
            ).sum()
        ),
        "weak_evidence_count": int(
            (
                results_df["evidence_quality"]
                == "WEAK"
            ).sum()
        ),
    }

    # ========================================================
    # RANGE COVERAGE
    # ========================================================

    range_valid = results_df[
        results_df["evidence_low"].notna()
        &
        results_df["evidence_high"].notna()
    ].copy()

    if len(range_valid) > 0:

        range_coverage = (
            range_valid[
                "actual_inside_evidence_range"
            ].mean()
            * 100
        )

    else:

        range_coverage = np.nan

    coverage[
        "evidence_range_coverage_pct"
    ] = float(range_coverage)

    # ========================================================
    # EVIDENCE QUALITY METRICS
    # ========================================================

    evidence_metrics = {}

    for quality in [
        "STRONG",
        "MODERATE",
        "WEAK",
    ]:

        subset = results_df[
            results_df["evidence_quality"]
            == quality
        ].copy()

        evidence_metrics[quality] = {
            "count": int(len(subset))
        }

        if len(subset) > 0:

            metrics = calculate_metrics(
                subset,
                "hybrid_value"
            )

            evidence_metrics[quality][
                "hybrid_metrics"
            ] = metrics

    # ========================================================
    # CITY METRICS
    # ========================================================

    city_metrics = []

    for city, city_data in results_df.groupby(
        "city"
    ):

        metrics = calculate_metrics(
            city_data,
            "hybrid_value"
        )

        if metrics is None:
            continue

        city_metrics.append(
            {
                "city": city,
                **metrics,
            }
        )

    city_metrics_df = pd.DataFrame(
        city_metrics
    )

    city_metrics_path = (
        OUTPUT_DIR
        / "hybrid_backtest_city_metrics.csv"
    )

    city_metrics_df.to_csv(
        city_metrics_path,
        index=False
    )

    # ========================================================
    # MODEL COMPARISON TABLE
    # ========================================================

    comparison_rows = []

    for method_name, metrics in overall_metrics.items():

        if metrics is None:
            continue

        comparison_rows.append(
            {
                "method": method_name,
                **metrics,
            }
        )

    comparison_df = pd.DataFrame(
        comparison_rows
    )

    comparison_path = (
        OUTPUT_DIR
        / "hybrid_backtest_model_comparison.csv"
    )

    comparison_df.to_csv(
        comparison_path,
        index=False
    )

    # ========================================================
    # REPORT
    # ========================================================

    report = {
        "methodology": {
            "comparable_weight": COMPARABLE_WEIGHT,
            "locality_weight": LOCALITY_WEIGHT,
            "ml_weight": ML_WEIGHT,
            "area_tolerance": AREA_TOLERANCE,
            "bedroom_tolerance": BEDROOM_TOLERANCE,
            "bathroom_tolerance": BATHROOM_TOLERANCE,
            "minimum_comparables": (
                MIN_COMPARABLES_FOR_DIRECT_USE
            ),
            "tier_1": (
                "same locality + <=5 km"
            ),
            "tier_2": (
                "different locality + <=5 km"
            ),
            "tier_3": (
                "5-15 km fallback"
            ),
            "tier_4": (
                ">15 km excluded"
            ),
            "target_excluded_from_comparables": True,
            "target_excluded_from_locality_statistics": True,
            "validation_type": (
                "cross-sectional backtest"
            ),
        },

        "dataset": {
            "input_rows": int(len(df)),
            "eligible_rows": int(len(eligible)),
        },

        "coverage": coverage,

        "overall_metrics": overall_metrics,

        "evidence_quality_metrics": evidence_metrics,
    }

    report_path = (
        OUTPUT_DIR
        / "hybrid_backtest_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4,
            default=str
        )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n")
    print("=" * 80)
    print("BACKTEST SUMMARY")
    print("=" * 80)

    print(
        f"\nEligible properties       : "
        f"{len(results_df):,}"
    )

    print(
        f"Hybrid valid predictions  : "
        f"{len(hybrid_valid):,}"
    )

    print(
        f"Hybrid coverage           : "
        f"{coverage['hybrid_coverage_pct']:.2f}%"
    )

    print(
        f"Evidence range coverage  : "
        f"{coverage['evidence_range_coverage_pct']:.2f}%"
    )

    print("\nEvidence quality:")
    print(
        f"  STRONG   : "
        f"{coverage['strong_evidence_count']:,}"
    )
    print(
        f"  MODERATE : "
        f"{coverage['moderate_evidence_count']:,}"
    )
    print(
        f"  WEAK     : "
        f"{coverage['weak_evidence_count']:,}"
    )

    print("\nOutput files:")
    print(
        f"  Property results : "
        f"{results_path}"
    )
    print(
        f"  City metrics     : "
        f"{city_metrics_path}"
    )
    print(
        f"  Model comparison : "
        f"{comparison_path}"
    )
    print(
        f"  Full report      : "
        f"{report_path}"
    )

    print("\n")
    print("=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()