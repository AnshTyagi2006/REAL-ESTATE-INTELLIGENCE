from pathlib import Path
import sys
import json

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = (
    ROOT
    / "data"
    / "modeling"
    / "valuation_modeling_dataset.csv"
)

MODEL_PATH = (
    ROOT
    / "data"
    / "models"
    / "lightgbm_tuned"
    / "lightgbm_tuned_model.joblib"
)

CALIBRATOR_PATH = (
    ROOT
    / "data"
    / "valuation"
    / "final_valuation_calibrator.joblib"
)

OUTPUT_DIR = ROOT / "data" / "valuation"


def money(value):
    if value is None or pd.isna(value):
        return "N/A"

    if value >= 10_000_000:
        return f"₹{value / 10_000_000:.2f} Cr"

    if value >= 100_000:
        return f"₹{value / 100_000:.2f} L"

    return f"₹{value:,.0f}"


def haversine_km(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    dlat = lat2 - lat1
    dlon = np.radians(lon2 - lon1)

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    return 6371 * 2 * np.arcsin(np.sqrt(a))


def get_comparable_value(target, pool):

    candidates = pool[
        (pool["city"] == target["city"])
        & (
            pool["valuation_area_sqft"].between(
                target["valuation_area_sqft"] * 0.80,
                target["valuation_area_sqft"] * 1.20,
            )
        )
        & (
            abs(
                pool["bedrooms"]
                - target["bedrooms"]
            ) <= 1
        )
        & (
            abs(
                pool["bathrooms"]
                - target["bathrooms"]
            ) <= 1
        )
    ].copy()

    if len(candidates) == 0:
        return np.nan, 0

    candidates["distance_km"] = haversine_km(
        target["latitude"],
        target["longitude"],
        candidates["latitude"].values,
        candidates["longitude"].values,
    )

    candidates["same_locality"] = (
        candidates["locality"]
        == target["locality"]
    )

    # Geographic tiers
    tier1 = candidates[
        candidates["same_locality"]
        & (candidates["distance_km"] <= 5)
    ]

    tier2 = candidates[
        (~candidates["same_locality"])
        & (candidates["distance_km"] <= 5)
    ]

    tier3 = candidates[
        (candidates["distance_km"] > 5)
        & (candidates["distance_km"] <= 15)
    ]

    if len(tier1) >= 5:
        selected = tier1

    elif len(
        pd.concat([tier1, tier2])
    ) >= 5:
        selected = pd.concat(
            [tier1, tier2]
        )

    elif len(
        pd.concat([tier1, tier2, tier3])
    ) >= 5:
        selected = pd.concat(
            [tier1, tier2, tier3]
        )

    else:
        return np.nan, 0

    selected = (
        selected
        .sort_values("distance_km")
        .head(20)
        .copy()
    )

    selected["ppsf"] = (
        selected["asking_price_inr"]
        / selected["valuation_area_sqft"]
    )

    selected = selected.replace(
        [np.inf, -np.inf],
        np.nan
    )

    selected = selected.infer_objects(
        copy=False
    )

    selected = selected.dropna(
        subset=["ppsf"]
    )

    if len(selected) < 3:
        return np.nan, len(selected)

    # IQR outlier filtering
    q1 = selected["ppsf"].quantile(0.25)
    q3 = selected["ppsf"].quantile(0.75)
    iqr = q3 - q1

    selected = selected[
        selected["ppsf"].between(
            q1 - 1.5 * iqr,
            q3 + 1.5 * iqr
        )
    ]

    if len(selected) < 3:
        return np.nan, len(selected)

    comparable_ppsf = selected["ppsf"].median()

    value = (
        comparable_ppsf
        * target["valuation_area_sqft"]
    )

    return value, len(selected)


def get_locality_value(target, pool):

    data = pool[
        (pool["city"] == target["city"])
        & (
            pool["locality"]
            == target["locality"]
        )
    ].copy()

    if len(data) == 0:
        return np.nan, 0

    data["ppsf"] = (
        data["asking_price_inr"]
        / data["valuation_area_sqft"]
    )

    data = data.replace(
        [np.inf, -np.inf],
        np.nan
    )

    data = data.infer_objects(
        copy=False
    )

    data = data.dropna(
        subset=["ppsf"]
    )

    same_bhk = data[
        data["bedrooms"]
        == target["bedrooms"]
    ]

    if len(same_bhk) >= 3:
        data = same_bhk

    if len(data) == 0:
        return np.nan, 0

    locality_ppsf = data["ppsf"].median()

    value = (
        locality_ppsf
        * target["valuation_area_sqft"]
    )

    return value, len(data)


def calculate_ml_value(target, model):

    features = [
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

    X = target[features].to_frame().T.copy()

    numeric_features = [
        "valuation_area_sqft",
        "bedrooms",
        "bathrooms",
        "latitude",
        "longitude",
        "floor",
        "total_floors",
    ]

    for column in numeric_features:
        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

    categorical_features = [
        "city",
        "locality",
        "property_type",
    ]

    for column in categorical_features:
        X[column] = X[column].astype(
            "category"
        )

    # Match the categories used during LightGBM training
    booster = model.booster_

    categorical_indices = (
        booster.pandas_categorical
    )

    for column, categories in zip(
        categorical_features,
        categorical_indices
    ):
        X[column] = pd.Categorical(
            X[column],
            categories=categories
        )

    prediction_log = model.predict(X)[0]

    return np.expm1(
        prediction_log
    )


def calculate_property_valuation(property_id):

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    df = pd.read_csv(DATA_PATH)

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
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # --------------------------------------------------------
    # Find target property
    # --------------------------------------------------------

    target_rows = df[
        df["property_id"]
        == property_id
    ]

    if target_rows.empty:
        return None

    target = target_rows.iloc[0]

    # Remove target from comparable pool
    pool = df[
        df["property_id"]
        != property_id
    ].copy()

    # --------------------------------------------------------
    # Load ML model
    # --------------------------------------------------------

    model = joblib.load(
        MODEL_PATH
    )

    # --------------------------------------------------------
    # ML valuation
    # --------------------------------------------------------

    ml_value = calculate_ml_value(
        target,
        model
    )

    # --------------------------------------------------------
    # Comparable valuation
    # --------------------------------------------------------

    comparable_value, comparable_count = (
        get_comparable_value(
            target,
            pool
        )
    )

    # --------------------------------------------------------
    # Locality valuation
    # --------------------------------------------------------

    locality_value, locality_count = (
        get_locality_value(
            target,
            pool
        )
    )

    # --------------------------------------------------------
    # Calibrated final valuation
    # --------------------------------------------------------

    final_value = np.nan

    if (
        not pd.isna(comparable_value)
        and not pd.isna(locality_value)
    ):

        calibrator = joblib.load(
            CALIBRATOR_PATH
        )

        signal_data = pd.DataFrame(
            {
                "ml_oof_value": [ml_value],
                "comparable_value": [
                    comparable_value
                ],
                "locality_value": [
                    locality_value
                ],
            }
        )

        final_value = np.expm1(
            calibrator.predict(
                np.log1p(signal_data)
            )[0]
        )

    # --------------------------------------------------------
    # Asking price analysis
    # --------------------------------------------------------

    asking_price = target[
        "asking_price_inr"
    ]

    premium_pct = np.nan

    if (
        not pd.isna(final_value)
        and final_value > 0
        and not pd.isna(asking_price)
    ):

        premium_pct = (
            (
                asking_price
                - final_value
            )
            / final_value
            * 100
        )

    # --------------------------------------------------------
    # Asking price classification
    # --------------------------------------------------------

    if pd.isna(premium_pct):

        price_signal = "Unavailable"

    elif premium_pct <= -15:

        price_signal = "Significant discount"

    elif premium_pct < -5:

        price_signal = "Moderate discount"

    elif premium_pct <= 5:

        price_signal = "Near estimated value"

    elif premium_pct <= 15:

        price_signal = "Moderate premium"

    else:

        price_signal = "Significant premium"

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "property_id": property_id,

        "city": str(
            target["city"]
        ),

        "locality": str(
            target["locality"]
        ),

        "valuation_area_sqft": (
            float(
                target[
                    "valuation_area_sqft"
                ]
            )
            if not pd.isna(
                target[
                    "valuation_area_sqft"
                ]
            )
            else None
        ),

        "bedrooms": (
            float(target["bedrooms"])
            if not pd.isna(
                target["bedrooms"]
            )
            else None
        ),

        "bathrooms": (
            float(target["bathrooms"])
            if not pd.isna(
                target["bathrooms"]
            )
            else None
        ),

        "asking_price_inr": (
            float(asking_price)
            if not pd.isna(asking_price)
            else None
        ),

        "ml_value": (
            float(ml_value)
            if not pd.isna(ml_value)
            else None
        ),

        "comparable_value": (
            float(comparable_value)
            if not pd.isna(comparable_value)
            else None
        ),

        "locality_value": (
            float(locality_value)
            if not pd.isna(locality_value)
            else None
        ),

        "final_estimated_value": (
            float(final_value)
            if not pd.isna(final_value)
            else None
        ),

        "asking_price_premium_pct": (
            float(premium_pct)
            if not pd.isna(premium_pct)
            else None
        ),

        "price_signal": price_signal,

        "comparable_count": int(
            comparable_count
        ),

        "locality_property_count": int(
            locality_count
        ),
    }

    return result


def save_valuation_result(result):

    property_id = result[
        "property_id"
    ]

    output_path = (
        OUTPUT_DIR
        / f"valuation_{property_id}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4
        )

    return output_path


def print_valuation_result(result):

    print("=" * 70)
    print("PROPERTY VALUATION")
    print("=" * 70)

    print(
        f"\nProperty ID : "
        f"{result['property_id']}"
    )

    print(
        f"City        : "
        f"{result['city']}"
    )

    print(
        f"Locality    : "
        f"{result['locality']}"
    )

    print(
        f"Area        : "
        f"{result['valuation_area_sqft']:,.0f} sqft"
    )

    print(
        f"Bedrooms    : "
        f"{result['bedrooms']}"
    )

    print(
        f"Bathrooms   : "
        f"{result['bathrooms']}"
    )

    print("\nVALUATION")
    print("-" * 50)

    print(
        f"ML valuation        : "
        f"{money(result['ml_value'])}"
    )

    print(
        f"Comparable valuation: "
        f"{money(result['comparable_value'])}"
    )

    print(
        f"Locality valuation  : "
        f"{money(result['locality_value'])}"
    )

    print(
        f"Final valuation     : "
        f"{money(result['final_estimated_value'])}"
    )

    print("\nASKING PRICE")
    print("-" * 50)

    print(
        f"Asking price        : "
        f"{money(result['asking_price_inr'])}"
    )

    if (
        result[
            "asking_price_premium_pct"
        ] is not None
    ):

        print(
            f"Premium / discount  : "
            f"{result['asking_price_premium_pct']:+.2f}%"
        )

    print(
        f"Price signal        : "
        f"{result['price_signal']}"
    )

    print(
        f"\nComparable count    : "
        f"{result['comparable_count']}"
    )

    print(
        f"Locality properties : "
        f"{result['locality_property_count']}"
    )


def main():

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "python src/valuation/"
            "run_property_valuation.py "
            "PROPERTY_ID"
        )

        return

    property_id = sys.argv[1]

    result = calculate_property_valuation(
        property_id
    )

    if result is None:

        print(
            f"Property {property_id} "
            f"not found."
        )

        return

    print_valuation_result(
        result
    )

    output_path = save_valuation_result(
        result
    )

    print(
        f"\nSaved: {output_path}"
    )


if __name__ == "__main__":
    main()