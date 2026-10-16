import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap


# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = (
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


# --------------------------------------------------
# MODEL FEATURES
# --------------------------------------------------

FEATURES = [
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


NUMERIC_FEATURES = [
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "floor",
    "total_floors",
]


CATEGORICAL_FEATURES = [
    "city",
    "locality",
    "property_type",
]


# --------------------------------------------------
# FEATURE LABELS
# --------------------------------------------------

FEATURE_LABELS = {
    "valuation_area_sqft": "Property area",
    "city": "City",
    "locality": "Locality",
    "bedrooms": "Bedrooms",
    "bathrooms": "Bathrooms",
    "latitude": "Location latitude",
    "longitude": "Location longitude",
    "property_type": "Property type",
    "floor": "Floor",
    "total_floors": "Total floors",
}


# --------------------------------------------------
# LOAD DATA AND MODEL
# --------------------------------------------------

df = pd.read_csv(DATASET_PATH)

model = joblib.load(MODEL_PATH)


# --------------------------------------------------
# PREPARE PROPERTY FEATURES
# --------------------------------------------------

def prepare_property_features(property_id):

    property_rows = df[
        df["property_id"].astype(str) == str(property_id)
    ]

    if property_rows.empty:
        return None

    row = property_rows.iloc[0]

    X = row[FEATURES].to_frame().T.copy()

    # Numeric columns
    for column in NUMERIC_FEATURES:

        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

    # Match LightGBM categorical categories
    try:

        pandas_categories = (
            model.booster_.pandas_categorical
        )

        for index, column in enumerate(
            CATEGORICAL_FEATURES
        ):

            if index < len(pandas_categories):

                categories = pandas_categories[index]

                X[column] = pd.Categorical(
                    X[column],
                    categories=categories
                )

    except Exception:

        for column in CATEGORICAL_FEATURES:

            X[column] = X[column].astype("category")

    return X


# --------------------------------------------------
# CALCULATE SHAP EXPLANATION
# --------------------------------------------------

def calculate_property_explanation(property_id):

    X = prepare_property_features(property_id)

    if X is None:
        return None

    # SHAP TreeExplainer
    explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(X)

    # One property = one row
    values = shap_values[0]

    positive_factors = []
    negative_factors = []
    all_factors = []

    for index, feature in enumerate(FEATURES):

        shap_value = float(values[index])

        value = X.iloc[0][feature]

        # Convert category / numpy values to readable value
        if pd.isna(value):
            readable_value = None
        else:
            readable_value = str(value)

        factor = {
            "feature": feature,
            "label": FEATURE_LABELS.get(
                feature,
                feature
            ),
            "value": readable_value,
            "shap_value": shap_value,
            "direction": (
                "increases"
                if shap_value > 0
                else "decreases"
            ),
            "absolute_impact": abs(shap_value),
        }

        all_factors.append(factor)

        if shap_value > 0:
            positive_factors.append(factor)

        elif shap_value < 0:
            negative_factors.append(factor)

    # Strongest factors first
    positive_factors.sort(
        key=lambda x: x["absolute_impact"],
        reverse=True
    )

    negative_factors.sort(
        key=lambda x: x["absolute_impact"],
        reverse=True
    )

    all_factors.sort(
        key=lambda x: x["absolute_impact"],
        reverse=True
    )

    # Model prediction
    prediction_log = float(
        model.predict(X)[0]
    )

    ml_predicted_value = float(
        np.expm1(prediction_log)
    )

    expected_value = explainer.expected_value

    if isinstance(expected_value, np.ndarray):
        expected_value = expected_value[0]

    return {
        "property_id": str(property_id),
        "ml_predicted_value": ml_predicted_value,
        "base_prediction_log": float(expected_value),
        "top_positive_factors": positive_factors[:5],
        "top_negative_factors": negative_factors[:5],
        "all_feature_contributions": all_factors,
    }


# --------------------------------------------------
# COMMAND-LINE MODE
# --------------------------------------------------

def main():

    if len(sys.argv) < 2:

        print(
            "Usage: "
            "python explain_property_valuation.py "
            "<property_id>"
        )

        return

    property_id = sys.argv[1]

    result = calculate_property_explanation(
        property_id
    )

    if result is None:

        print(
            f"Property not found: {property_id}"
        )

        return

    print("\nPROPERTY-SPECIFIC ML EXPLANATION\n")

    print(
        f"Property ID : "
        f"{result['property_id']}"
    )

    print(
        f"ML valuation: "
        f"₹{result['ml_predicted_value']:,.0f}"
    )

    print("\nFACTORS INCREASING ML VALUE")

    for factor in result["top_positive_factors"]:

        print(
            f"{factor['label']:<25}"
            f"{factor['value']:<25}"
            f"SHAP: "
            f"{factor['shap_value']:+.4f}"
        )

    print("\nFACTORS DECREASING ML VALUE")

    for factor in result["top_negative_factors"]:

        print(
            f"{factor['label']:<25}"
            f"{factor['value']:<25}"
            f"SHAP: "
            f"{factor['shap_value']:+.4f}"
        )


if __name__ == "__main__":
    main()