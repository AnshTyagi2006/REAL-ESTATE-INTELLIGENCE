from pathlib import Path
import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = ROOT / "data" / "valuation" / "hybrid_oof_results.csv"
CALIBRATOR_PATH = (
    ROOT
    / "data"
    / "valuation"
    / "final_valuation_calibrator.joblib"
)

OUTPUT_PATH = (
    ROOT
    / "data"
    / "valuation"
    / "asking_price_anomaly_results.csv"
)


def classify_premium(premium_pct):

    if premium_pct <= -15:
        return "Significant discount"

    if premium_pct <= -5:
        return "Moderate discount"

    if premium_pct < 5:
        return "Near estimated value"

    if premium_pct < 15:
        return "Moderate premium"

    return "Significant premium"


def main():

    print("=" * 70)
    print("ASKING-PRICE ANOMALY ENGINE")
    print("=" * 70)

    df = pd.read_csv(DATA_PATH)

    # Only properties with all three valuation signals
    data = df.dropna(
        subset=[
            "actual_price",
            "ml_oof_value",
            "comparable_value",
            "locality_value",
        ]
    ).copy()

    print(
        f"\nProperties analyzed: {len(data):,}"
    )

    # --------------------------------------------------------
    # Load calibrated combination model
    # --------------------------------------------------------

    calibrator = joblib.load(
        CALIBRATOR_PATH
    )

    signals = [
        "ml_oof_value",
        "comparable_value",
        "locality_value",
    ]

    X = np.log1p(
        data[signals]
    )

    # Final estimated value
    data["estimated_fair_value"] = np.expm1(
        calibrator.predict(X)
    )

    # --------------------------------------------------------
    # Asking-price premium / discount
    # --------------------------------------------------------

    data["asking_price_difference"] = (
        data["actual_price"]
        - data["estimated_fair_value"]
    )

    data["asking_price_difference_pct"] = (
        data["asking_price_difference"]
        / data["estimated_fair_value"]
        * 100
    )

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    data["price_signal"] = (
        data["asking_price_difference_pct"]
        .apply(classify_premium)
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    columns = [
        "property_id",
        "city",
        "locality",
        "actual_price",
        "ml_oof_value",
        "comparable_value",
        "locality_value",
        "estimated_fair_value",
        "asking_price_difference",
        "asking_price_difference_pct",
        "price_signal",
    ]

    result = data[columns].copy()

    result.to_csv(
        OUTPUT_PATH,
        index=False
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\nPRICE SIGNAL DISTRIBUTION")
    print("-" * 50)

    print(
        result["price_signal"]
        .value_counts()
        .to_string()
    )

    print("\nAverage asking-price difference:")
    print(
        f"{result['asking_price_difference_pct'].mean():.2f}%"
    )

    print("\nOutput:")
    print(OUTPUT_PATH)

    print("\n")
    print("=" * 70)
    print("ANOMALY ENGINE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
    