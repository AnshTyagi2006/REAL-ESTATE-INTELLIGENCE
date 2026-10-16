from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "data" / "valuation" / "hybrid_oof_results.csv"
OUTPUT = ROOT / "data" / "valuation"


def metrics(df, prediction_col):
    df = df[df[prediction_col].notna()].copy()

    if len(df) == 0:
        return None

    error = df[prediction_col] - df["actual_price"]
    ape = abs(error) / df["actual_price"] * 100

    return {
        "n": len(df),
        "mae": abs(error).mean(),
        "median_abs_pct": ape.median(),
        "mean_abs_pct": ape.mean(),
        "bias": error.mean(),
    }


def main():

    print("=" * 70)
    print("HYBRID OOF DIAGNOSTIC ANALYSIS")
    print("=" * 70)

    df = pd.read_csv(INPUT)

    # --------------------------------------------------------
    # Compare Hybrid vs ML for every property
    # --------------------------------------------------------

    df["ml_abs_pct"] = (
        abs(df["ml_oof_value"] - df["actual_price"])
        / df["actual_price"]
        * 100
    )

    df["hybrid_abs_pct"] = (
        abs(df["hybrid_v1_value"] - df["actual_price"])
        / df["actual_price"]
        * 100
    )

    valid = df[
        df["ml_oof_value"].notna()
        & df["hybrid_v1_value"].notna()
    ].copy()

    valid["hybrid_improvement_pct_points"] = (
        valid["ml_abs_pct"]
        - valid["hybrid_abs_pct"]
    )

    # Positive = Hybrid improved ML
    # Negative = Hybrid was worse

    improved = (
        valid["hybrid_improvement_pct_points"] > 0
    )

    print("\nPROPERTY-LEVEL COMPARISON")
    print("-" * 50)

    print(
        f"Valid ML + Hybrid properties : {len(valid):,}"
    )

    print(
        f"Hybrid improved ML           : "
        f"{improved.sum():,} "
        f"({improved.mean() * 100:.2f}%)"
    )

    print(
        f"Hybrid worse than ML         : "
        f"{(~improved).sum():,} "
        f"({(~improved).mean() * 100:.2f}%)"
    )

    print(
        f"Average error improvement    : "
        f"{valid['hybrid_improvement_pct_points'].mean():.2f} "
        f"percentage points"
    )

    # --------------------------------------------------------
    # Evidence quality
    #
    # Evidence quality is reconstructed from available
    # comparable/locality information.
    # --------------------------------------------------------

    def evidence_quality(row):

        comparable = row["comparable_value"]
        locality = row["locality_value"]

        if pd.isna(comparable) or pd.isna(locality):
            return "WEAK"

        return "AVAILABLE"

    valid["evidence_status"] = valid.apply(
        evidence_quality,
        axis=1
    )

    # --------------------------------------------------------
    # City-level comparison
    # --------------------------------------------------------

    city_rows = []

    for city, group in valid.groupby("city"):

        ml = metrics(group, "ml_oof_value")
        hybrid = metrics(group, "hybrid_v1_value")

        if ml is None or hybrid is None:
            continue

        city_rows.append({
            "city": city,
            "n": len(group),
            "ml_mae": ml["mae"],
            "hybrid_mae": hybrid["mae"],
            "ml_median_pct": ml["median_abs_pct"],
            "hybrid_median_pct": hybrid["median_abs_pct"],
            "ml_mean_pct": ml["mean_abs_pct"],
            "hybrid_mean_pct": hybrid["mean_abs_pct"],
            "mae_change": hybrid["mae"] - ml["mae"],
            "median_pct_change":
                hybrid["median_abs_pct"]
                - ml["median_abs_pct"],
        })

    city_df = pd.DataFrame(city_rows)

    city_df = city_df.sort_values(
        "mae_change"
    )

    city_path = (
        OUTPUT
        / "hybrid_oof_city_diagnostic.csv"
    )

    city_df.to_csv(
        city_path,
        index=False
    )

    print("\nCITY RESULTS")
    print("-" * 50)

    print(
        city_df[
            [
                "city",
                "n",
                "ml_mae",
                "hybrid_mae",
                "mae_change",
            ]
        ].to_string(index=False)
    )

    # --------------------------------------------------------
    # Strong vs weaker evidence
    #
    # Use comparable count inferred from whether comparable
    # valuation exists and locality valuation exists.
    # --------------------------------------------------------

    valid["comparable_available"] = (
        valid["comparable_value"].notna()
    )

    valid["locality_available"] = (
        valid["locality_value"].notna()
    )

    valid["evidence_group"] = np.select(
        [
            valid["comparable_available"]
            & valid["locality_available"],

            valid["comparable_available"]
            | valid["locality_available"],
        ],
        [
            "Both comparable + locality",
            "Only one market signal",
        ],
        default="ML only",
    )

    evidence_rows = []

    for group_name, group in valid.groupby(
        "evidence_group"
    ):

        ml = metrics(group, "ml_oof_value")
        hybrid = metrics(group, "hybrid_v1_value")

        if ml is None or hybrid is None:
            continue

        evidence_rows.append({
            "evidence_group": group_name,
            "n": len(group),
            "ml_mae": ml["mae"],
            "hybrid_mae": hybrid["mae"],
            "ml_median_pct": ml["median_abs_pct"],
            "hybrid_median_pct":
                hybrid["median_abs_pct"],
            "mae_change":
                hybrid["mae"] - ml["mae"],
        })

    evidence_df = pd.DataFrame(
        evidence_rows
    )

    evidence_path = (
        OUTPUT
        / "hybrid_oof_evidence_diagnostic.csv"
    )

    evidence_df.to_csv(
        evidence_path,
        index=False
    )

    print("\nEVIDENCE RESULTS")
    print("-" * 50)

    print(
        evidence_df.to_string(index=False)
    )

    # --------------------------------------------------------
    # Biggest improvements / regressions
    # --------------------------------------------------------

    best = valid.sort_values(
        "hybrid_improvement_pct_points",
        ascending=False
    ).head(10)

    worst = valid.sort_values(
        "hybrid_improvement_pct_points"
    ).head(10)

    best.to_csv(
        OUTPUT / "hybrid_oof_best_improvements.csv",
        index=False
    )

    worst.to_csv(
        OUTPUT / "hybrid_oof_worst_regressions.csv",
        index=False
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(
        f"\nHybrid improves ML for "
        f"{improved.mean() * 100:.2f}% "
        f"of comparable+hybrid cases."
    )

    print(
        f"Average absolute-error improvement: "
        f"{valid['hybrid_improvement_pct_points'].mean():.2f} "
        f"percentage points."
    )

    print("\nFiles created:")

    print(f"  {city_path}")
    print(f"  {evidence_path}")
    print(
        f"  {OUTPUT / 'hybrid_oof_best_improvements.csv'}"
    )
    print(
        f"  {OUTPUT / 'hybrid_oof_worst_regressions.csv'}"
    )


if __name__ == "__main__":
    main()