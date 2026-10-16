from pathlib import Path
import numpy as np
import pandas as pd

from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.metrics import mean_absolute_error, mean_squared_error


ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "data" / "valuation" / "hybrid_oof_results.csv"
OUTPUT = ROOT / "data" / "valuation"


def main():

    print("=" * 70)
    print("VALUATION SIGNAL CALIBRATION")
    print("=" * 70)

    df = pd.read_csv(INPUT)

    # --------------------------------------------------------
    # Only records having all three valuation signals
    # --------------------------------------------------------

    data = df.dropna(
        subset=[
            "actual_price",
            "ml_oof_value",
            "comparable_value",
            "locality_value",
        ]
    ).copy()

    print(
        f"\nProperties with all three signals: "
        f"{len(data):,}"
    )

    # --------------------------------------------------------
    # Features
    #
    # Log transform keeps the three price signals on a
    # comparable scale and reduces the influence of very
    # expensive properties.
    # --------------------------------------------------------

    X = np.log1p(
        data[
            [
                "ml_oof_value",
                "comparable_value",
                "locality_value",
            ]
        ]
    )

    y = np.log1p(
        data["actual_price"]
    )

    # --------------------------------------------------------
    # Cross-validated calibration
    #
    # The calibration model also needs out-of-sample
    # validation so we don't judge it on the same records
    # used to fit it.
    # --------------------------------------------------------

    kfold = KFold(
        n_splits=5,
        shuffle=True,
        random_state=42,
    )

    model = Ridge(
        alpha=10.0
    )

    predictions_log = cross_val_predict(
        model,
        X,
        y,
        cv=kfold,
    )

    predictions = np.expm1(
        predictions_log
    )

    actual = data[
        "actual_price"
    ].values

    errors = predictions - actual

    ape = (
        abs(errors)
        / actual
        * 100
    )

    mae = mean_absolute_error(
        actual,
        predictions
    )

    rmse = np.sqrt(
        mean_squared_error(
            actual,
            predictions
        )
    )

    print("\nCALIBRATED MODEL")
    print("-" * 50)

    print(
        f"MAE                : ₹{mae:,.0f}"
    )

    print(
        f"RMSE               : ₹{rmse:,.0f}"
    )

    print(
        f"Mean Abs % Error   : {ape.mean():.2f}%"
    )

    print(
        f"Median Abs % Error : {np.median(ape):.2f}%"
    )

    print(
        f"Mean Bias          : ₹{errors.mean():,.0f}"
    )

    # --------------------------------------------------------
    # Fit final calibration model on all available records
    # --------------------------------------------------------

    model.fit(X, y)

    coefficients = pd.DataFrame({
        "signal": [
            "ML",
            "Comparable",
            "Locality",
        ],
        "coefficient": model.coef_,
    })

    print("\nCALIBRATION COEFFICIENTS")
    print("-" * 50)

    print(
        coefficients.to_string(
            index=False
        )
    )

    print(
        f"\nIntercept: "
        f"{model.intercept_:.6f}"
    )

    # --------------------------------------------------------
    # Save calibration model
    # --------------------------------------------------------

    import joblib

    model_path = (
        OUTPUT
        / "valuation_signal_calibrator.joblib"
    )

    joblib.dump(
        model,
        model_path
    )

    # --------------------------------------------------------
    # Save validation predictions
    # --------------------------------------------------------

    validation = data[
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

    validation[
        "calibrated_value"
    ] = predictions

    validation[
        "absolute_error"
    ] = abs(errors)

    validation[
        "absolute_error_pct"
    ] = ape

    validation_path = (
        OUTPUT
        / "calibrated_valuation_validation.csv"
    )

    validation.to_csv(
        validation_path,
        index=False
    )

    coefficients.to_csv(
        OUTPUT
        / "valuation_signal_coefficients.csv",
        index=False
    )

    print("\nFiles created:")
    print(
        f"  {model_path}"
    )
    print(
        f"  {validation_path}"
    )
    print(
        f"  {OUTPUT / 'valuation_signal_coefficients.csv'}"
    )

    print("\n")
    print("=" * 70)
    print("CALIBRATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()