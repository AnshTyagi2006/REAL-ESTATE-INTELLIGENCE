from pathlib import Path
import warnings
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "data" / "valuation" / "hybrid_oof_results.csv"
OUTPUT = ROOT / "data" / "valuation"


def evaluate(actual, predicted):
    error = predicted - actual
    ape = abs(error) / actual * 100

    return {
        "n": len(actual),
        "mae": np.mean(abs(error)),
        "rmse": np.sqrt(np.mean(error ** 2)),
        "mean_abs_pct": np.mean(ape),
        "median_abs_pct": np.median(ape),
        "bias": np.mean(error),
    }


def main():

    print("=" * 70)
    print("STRICT HOLDOUT CALIBRATION VALIDATION")
    print("=" * 70)

    df = pd.read_csv(INPUT)

    data = df.dropna(
        subset=[
            "actual_price",
            "ml_oof_value",
            "comparable_value",
            "locality_value",
        ]
    ).copy()

    print(
        f"\nUsable records: {len(data):,}"
    )

    train, test = train_test_split(
        data,
        test_size=0.20,
        random_state=42,
    )

    print(
        f"Calibration set : {len(train):,}"
    )
    print(
        f"Holdout set     : {len(test):,}"
    )

    signals = [
        "ml_oof_value",
        "comparable_value",
        "locality_value",
    ]

    X_train = np.log1p(
        train[signals]
    )

    y_train = np.log1p(
        train["actual_price"]
    )

    X_test = np.log1p(
        test[signals]
    )

    y_test = test[
        "actual_price"
    ]

    # --------------------------------------------------------
    # Fit calibration model ONLY on calibration set
    # --------------------------------------------------------

    calibrator = Ridge(
        alpha=10.0
    )

    calibrator.fit(
        X_train,
        y_train
    )

    predictions = np.expm1(
        calibrator.predict(X_test)
    )

    # --------------------------------------------------------
    # Final evaluation
    # --------------------------------------------------------

    result = evaluate(
        y_test.values,
        predictions
    )

    print("\nFINAL HOLDOUT PERFORMANCE")
    print("-" * 50)

    print(
        f"N                 : {result['n']:,}"
    )

    print(
        f"MAE               : ₹{result['mae']:,.0f}"
    )

    print(
        f"RMSE              : ₹{result['rmse']:,.0f}"
    )

    print(
        f"Mean Abs % Error  : "
        f"{result['mean_abs_pct']:.2f}%"
    )

    print(
        f"Median Abs % Error: "
        f"{result['median_abs_pct']:.2f}%"
    )

    print(
        f"Bias              : "
        f"₹{result['bias']:,.0f}"
    )

    # --------------------------------------------------------
    # Compare against individual signals
    # --------------------------------------------------------

    print("\nHOLDOUT BASELINES")
    print("-" * 50)

    for name, column in [
        ("ML OOF", "ml_oof_value"),
        ("Comparable", "comparable_value"),
        ("Locality", "locality_value"),
    ]:

        values = evaluate(
            test["actual_price"].values,
            test[column].values,
        )

        print(
            f"\n{name}"
        )

        print(
            f"MAE               : "
            f"₹{values['mae']:,.0f}"
        )

        print(
            f"Median Abs % Error: "
            f"{values['median_abs_pct']:.2f}%"
        )

    # --------------------------------------------------------
    # Save predictions
    # --------------------------------------------------------

    output = test[
        [
            "property_id",
            "city",
            "locality",
            "actual_price",
            "ml_oof_value",
            "comparable_value",
            "locality_value",
        ]
    ].copy()

    output[
        "calibrated_value"
    ] = predictions

    output[
        "absolute_error"
    ] = abs(
        predictions
        - output["actual_price"].values
    )

    output[
        "absolute_error_pct"
    ] = (
        output["absolute_error"]
        / output["actual_price"]
        * 100
    )

    output_path = (
        OUTPUT
        / "calibrated_holdout_predictions.csv"
    )

    output.to_csv(
        output_path,
        index=False
    )

    # --------------------------------------------------------
    # Save coefficients
    # --------------------------------------------------------

    coefficients = pd.DataFrame({
        "signal": [
            "ML",
            "Comparable",
            "Locality",
        ],
        "coefficient": calibrator.coef_,
    })

    coefficients.to_csv(
        OUTPUT
        / "final_calibration_coefficients.csv",
        index=False
    )

    joblib.dump(
        calibrator,
        OUTPUT
        / "final_valuation_calibrator.joblib"
    )

    print("\nFiles created:")
    print(output_path)

    print(
        OUTPUT
        / "final_calibration_coefficients.csv"
    )

    print(
        OUTPUT
        / "final_valuation_calibrator.joblib"
    )

    print("\n")
    print("=" * 70)
    print("STRICT HOLDOUT VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()