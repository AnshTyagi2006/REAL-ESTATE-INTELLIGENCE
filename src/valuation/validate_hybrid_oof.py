from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import KFold
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from lightgbm import LGBMRegressor

warnings.filterwarnings("ignore")


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = ROOT / "data" / "modeling" / "valuation_modeling_dataset.csv"
OUTPUT_DIR = ROOT / "data" / "valuation"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FEATURES
# ============================================================

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


# ============================================================
# TUNED LIGHTGBM PARAMETERS
# ============================================================

MODEL_PARAMS = {
    "n_estimators": 500,
    "learning_rate": 0.10,
    "num_leaves": 70,
    "min_child_samples": 20,
    "subsample": 0.7,
    "colsample_bytree": 0.7,
    "random_state": 42,
    "n_jobs": -1,
    "verbosity": -1,
}


# ============================================================
# HELPERS
# ============================================================

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


def ape(actual, predicted):
    return abs(predicted - actual) / actual * 100


def train_model(X_train, y_train):

    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median"))
    ])

    categorical_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        (
            "encoder",
            OneHotEncoder(
                handle_unknown="ignore"
            )
        ),
    ])

    preprocessor = ColumnTransformer([
        ("num", numeric_pipe, NUMERIC_FEATURES),
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),
    ])

    model = LGBMRegressor(**MODEL_PARAMS)

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("model", model),
    ])

    pipeline.fit(
        X_train,
        np.log1p(y_train)
    )

    return pipeline


# ============================================================
# COMPARABLE VALUATION
# ============================================================

def comparable_value(target, pool):

    candidates = pool[
        (pool["city"] == target["city"])
        &
        (
            pool["valuation_area_sqft"]
            .between(
                target["valuation_area_sqft"] * 0.80,
                target["valuation_area_sqft"] * 1.20
            )
        )
        &
        (
            abs(
                pool["bedrooms"]
                - target["bedrooms"]
            ) <= 1
        )
        &
        (
            abs(
                pool["bathrooms"]
                - target["bathrooms"]
            ) <= 1
        )
    ].copy()

    if len(candidates) == 0:
        return np.nan

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
    elif len(pd.concat([tier1, tier2])) >= 5:
        selected = pd.concat([tier1, tier2])
    elif len(pd.concat([tier1, tier2, tier3])) >= 5:
        selected = pd.concat([tier1, tier2, tier3])
    else:
        return np.nan

    selected = selected.sort_values(
        ["distance_km"]
    ).head(20)

    selected["ppsf"] = (
        selected["asking_price_inr"]
        / selected["valuation_area_sqft"]
    )

    selected = selected.replace(
        [np.inf, -np.inf],
        np.nan
    ).dropna(
        subset=["ppsf"]
    )

    if len(selected) < 3:
        return np.nan

    q1 = selected["ppsf"].quantile(0.25)
    q3 = selected["ppsf"].quantile(0.75)
    iqr = q3 - q1

    usable = selected[
        selected["ppsf"].between(
            q1 - 1.5 * iqr,
            q3 + 1.5 * iqr
        )
    ]

    if len(usable) < 3:
        usable = selected

    return (
        usable["ppsf"].median()
        * target["valuation_area_sqft"]
    )


# ============================================================
# LOCALITY VALUATION
# ============================================================

def locality_value(target, pool):

    data = pool[
        (pool["city"] == target["city"])
        &
        (pool["locality"] == target["locality"])
    ].copy()

    if len(data) == 0:
        return np.nan

    data["ppsf"] = (
        data["asking_price_inr"]
        / data["valuation_area_sqft"]
    )

    same_bhk = data[
        data["bedrooms"] == target["bedrooms"]
    ]

    if len(same_bhk) >= 3:
        data = same_bhk

    if len(data) == 0:
        return np.nan

    return (
        data["ppsf"].median()
        * target["valuation_area_sqft"]
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("OUT-OF-FOLD HYBRID VALUATION VALIDATION")
    print("=" * 70)

    df = pd.read_csv(DATA_PATH)

    numeric = [
        "asking_price_inr",
        "valuation_area_sqft",
        "bedrooms",
        "bathrooms",
        "latitude",
        "longitude",
        "floor",
        "total_floors",
    ]

    for col in numeric:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df[
        df["asking_price_inr"].notna()
        & (df["asking_price_inr"] > 0)
        & df[FEATURES].notna().all(axis=1)
    ].reset_index(drop=True)

    print(f"\nEligible properties: {len(df):,}")

    X = df[FEATURES]
    y = df["asking_price_inr"]

    oof_ml = np.zeros(len(df))

    kfold = KFold(
        n_splits=5,
        shuffle=True,
        random_state=42
    )

    print("\nGenerating 5-fold out-of-fold ML predictions...")

    for fold, (train_idx, valid_idx) in enumerate(
        kfold.split(X),
        start=1
    ):

        print(
            f"Fold {fold}/5 | "
            f"Train: {len(train_idx):,} | "
            f"Validation: {len(valid_idx):,}"
        )

        model = train_model(
            X.iloc[train_idx],
            y.iloc[train_idx]
        )

        predictions_log = model.predict(
            X.iloc[valid_idx]
        )

        oof_ml[valid_idx] = np.expm1(
            predictions_log
        )

    df["ml_oof_value"] = oof_ml

    print("\nCalculating comparable and locality values...")

    results = []

    for i, target in df.iterrows():

        pool = df.drop(
            index=i
        )

        comp = comparable_value(
            target,
            pool
        )

        loc = locality_value(
            target,
            pool
        )

        ml = target["ml_oof_value"]

        if (
            not pd.isna(comp)
            and not pd.isna(loc)
            and not pd.isna(ml)
        ):
            hybrid = (
                0.45 * comp
                + 0.35 * loc
                + 0.20 * ml
            )
        else:
            hybrid = np.nan

        actual = target["asking_price_inr"]

        results.append({
            "property_id": target["property_id"],
            "city": target["city"],
            "locality": target["locality"],
            "actual_price": actual,
            "ml_oof_value": ml,
            "comparable_value": comp,
            "locality_value": loc,
            "hybrid_v1_value": hybrid,
        })

        if (i + 1) % 500 == 0:
            print(
                f"Processed {i + 1:,}/{len(df):,}"
            )

    results = pd.DataFrame(results)

    results_path = (
        OUTPUT_DIR
        / "hybrid_oof_results.csv"
    )

    results.to_csv(
        results_path,
        index=False
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    methods = {
        "ML OOF": "ml_oof_value",
        "Comparable": "comparable_value",
        "Locality": "locality_value",
        "Hybrid V1": "hybrid_v1_value",
    }

    metrics = {}

    print("\n")
    print("=" * 70)
    print("OUT-OF-FOLD RESULTS")
    print("=" * 70)

    for name, column in methods.items():

        valid = results[
            results[column].notna()
        ]

        actual = valid["actual_price"]
        predicted = valid[column]

        error = predicted - actual

        mae = abs(error).mean()

        rmse = np.sqrt(
            np.mean(error ** 2)
        )

        mean_pct = (
            abs(error) / actual * 100
        ).mean()

        median_pct = (
            abs(error) / actual * 100
        ).median()

        bias = error.mean()

        metrics[name] = {
            "n": int(len(valid)),
            "mae_inr": float(mae),
            "rmse_inr": float(rmse),
            "mean_absolute_pct": float(mean_pct),
            "median_absolute_pct": float(median_pct),
            "mean_prediction_error_inr": float(bias),
        }

        print(f"\n{name}")
        print(f"N                 : {len(valid):,}")
        print(f"MAE               : ₹{mae:,.0f}")
        print(f"RMSE              : ₹{rmse:,.0f}")
        print(f"Mean Abs % Error  : {mean_pct:.2f}%")
        print(f"Median Abs % Error: {median_pct:.2f}%")
        print(f"Bias              : ₹{bias:,.0f}")

    comparison = pd.DataFrame(
        [
            {
                "method": name,
                **values
            }
            for name, values in metrics.items()
        ]
    )

    comparison.to_csv(
        OUTPUT_DIR
        / "hybrid_oof_model_comparison.csv",
        index=False
    )

    with open(
        OUTPUT_DIR
        / "hybrid_oof_report.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            metrics,
            f,
            indent=4
        )

    print("\n")
    print("=" * 70)
    print("OOF VALIDATION COMPLETE")
    print("=" * 70)

    print(
        f"\nResults saved to:\n"
        f"{results_path}"
    )


if __name__ == "__main__":
    main()