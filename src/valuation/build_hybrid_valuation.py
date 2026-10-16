from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd


# =========================================================
# CONFIGURATION
# =========================================================

DATA_PATH = Path(
    "data/modeling/valuation_modeling_dataset.csv"
)

MODEL_PATH = Path(
    "data/models/lightgbm_tuned/"
    "lightgbm_tuned_model.joblib"
)

COMPARABLE_SUMMARY_PATH = Path(
    "data/valuation/"
    "comparable_valuation_summary.json"
)

LOCALITY_SUMMARY_PATH = Path(
    "data/valuation/"
    "target_locality_market_intelligence.json"
)

OUTPUT_DIR = Path("data/valuation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_PROPERTY_ID = "RE-00000001"


# =========================================================
# V1 HYBRID WEIGHTS
# =========================================================
#
# These are transparent V1 engineering weights.
# They are NOT learned/calibrated weights yet.
#
# Comparable evidence:
# Strong property-specific evidence.
#
# Locality evidence:
# Broader market context.
#
# ML:
# Useful learned signal, but lower weight because
# unseen-locality validation showed weaker generalization.
# =========================================================

COMPARABLE_WEIGHT = 0.45
LOCALITY_WEIGHT = 0.35
ML_WEIGHT = 0.20


# =========================================================
# LOAD DATA
# =========================================================

df = pd.read_csv(DATA_PATH)


# =========================================================
# LOAD PREVIOUS RESULTS
# =========================================================

with open(
    COMPARABLE_SUMMARY_PATH,
    "r",
    encoding="utf-8"
) as f:

    comparable_summary = json.load(f)


with open(
    LOCALITY_SUMMARY_PATH,
    "r",
    encoding="utf-8"
) as f:

    locality_summary = json.load(f)


# =========================================================
# TARGET PROPERTY
# =========================================================

target_rows = df[
    df["property_id"] == TARGET_PROPERTY_ID
]

if target_rows.empty:
    raise ValueError(
        f"Target property {TARGET_PROPERTY_ID} not found."
    )

target = target_rows.iloc[0]


# =========================================================
# TARGET INFORMATION
# =========================================================

target_area = float(
    target["valuation_area_sqft"]
)

target_asking_price = float(
    target["asking_price_inr"]
)

target_city = target["city"]
target_locality = target["locality"]


print("=" * 90)
print("HYBRID PROPERTY VALUATION ENGINE")
print("=" * 90)

print(f"\nTarget Property : {TARGET_PROPERTY_ID}")
print(f"City            : {target_city}")
print(f"Locality        : {target_locality}")
print(f"Area            : {target_area:,.2f} sqft")
print(
    f"Current Asking  : "
    f"₹{target_asking_price:,.0f}"
)


# =========================================================
# 1. COMPARABLE SIGNAL
# =========================================================

comparable_value = float(
    comparable_summary[
        "weighted_median_value"
    ]
)

comparable_p25_value = float(
    comparable_summary[
        "p25_value"
    ]
)

comparable_p75_value = float(
    comparable_summary[
        "p75_value"
    ]
)

comparable_ppsf = float(
    comparable_summary[
        "weighted_median_ppsf"
    ]
)

same_locality_count = int(
    comparable_summary[
        "same_locality_comparable_count"
    ]
)

comparable_count = int(
    comparable_summary[
        "valuation_comparable_count"
    ]
)

comparable_evidence_level = (
    comparable_summary[
        "evidence_level"
    ]
)


# =========================================================
# 2. LOCALITY / 3-BHK SIGNAL
# =========================================================

bedroom_stats = locality_summary[
    "bedroom_specific_statistics"
]

if bedroom_stats is None:
    raise ValueError(
        "No bedroom-specific locality statistics available."
    )


locality_ppsf = float(
    bedroom_stats["median_ppsf"]
)

locality_value = (
    locality_ppsf
    * target_area
)

locality_p25_ppsf = float(
    bedroom_stats["p25_ppsf"]
)

locality_p75_ppsf = float(
    bedroom_stats["p75_ppsf"]
)

locality_p25_value = (
    locality_p25_ppsf
    * target_area
)

locality_p75_value = (
    locality_p75_ppsf
    * target_area
)

locality_property_count = int(
    bedroom_stats["property_count"]
)


# =========================================================
# 3. ML SIGNAL
# =========================================================

model = joblib.load(
    MODEL_PATH
)


feature_columns = [
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


categorical_columns = [
    "city",
    "locality",
    "property_type",
]


X_target = pd.DataFrame(
    [target[feature_columns]],
    columns=feature_columns
)


# Recreate categorical representation used during
# LightGBM training.

for column in categorical_columns:

    categories = (
        df[column]
        .dropna()
        .astype(str)
        .unique()
    )

    X_target[column] = (
        X_target[column]
        .astype(str)
    )

    X_target[column] = pd.Categorical(
        X_target[column],
        categories=categories
    )


predicted_log_price = model.predict(
    X_target
)[0]


ml_value = float(
    np.expm1(
        predicted_log_price
    )
)

ml_ppsf = (
    ml_value
    / target_area
)


# =========================================================
# DISPLAY THREE SIGNALS
# =========================================================

print("\n" + "=" * 90)
print("THREE VALUATION SIGNALS")
print("=" * 90)

print(
    f"Comparable valuation : "
    f"₹{comparable_value:,.0f}"
)

print(
    f"3-BHK locality value : "
    f"₹{locality_value:,.0f}"
)

print(
    f"ML valuation         : "
    f"₹{ml_value:,.0f}"
)


# =========================================================
# SIGNAL AGREEMENT
# =========================================================

signals = np.array([
    comparable_value,
    locality_value,
    ml_value,
])


signal_min = signals.min()
signal_max = signals.max()
signal_mean = signals.mean()

signal_spread = (
    signal_max
    - signal_min
)


signal_spread_pct = (
    signal_spread
    / signal_mean
) * 100


# Pairwise differences

comparable_locality_diff_pct = (
    abs(
        comparable_value
        - locality_value
    )
    / (
        (
            comparable_value
            + locality_value
        ) / 2
    )
) * 100


comparable_ml_diff_pct = (
    abs(
        comparable_value
        - ml_value
    )
    / (
        (
            comparable_value
            + ml_value
        ) / 2
    )
) * 100


locality_ml_diff_pct = (
    abs(
        locality_value
        - ml_value
    )
    / (
        (
            locality_value
            + ml_value
        ) / 2
    )
) * 100


# =========================================================
# AGREEMENT INTERPRETATION
# =========================================================

if signal_spread_pct <= 5:

    agreement_level = "STRONG"

elif signal_spread_pct <= 10:

    agreement_level = "MODERATE"

elif signal_spread_pct <= 20:

    agreement_level = "MIXED"

else:

    agreement_level = "DIVERGENT"


# =========================================================
# HYBRID VALUE
# =========================================================

hybrid_value = (
    COMPARABLE_WEIGHT
    * comparable_value
    +
    LOCALITY_WEIGHT
    * locality_value
    +
    ML_WEIGHT
    * ml_value
)


hybrid_ppsf = (
    hybrid_value
    / target_area
)


# =========================================================
# HYBRID RANGE
# =========================================================
#
# We use the comparable P25-P75 range as the primary
# observed market range because comparable evidence
# is the strongest property-specific evidence.
#
# We then check whether the hybrid central estimate
# sits inside that observed range.
# =========================================================

range_low = comparable_p25_value
range_high = comparable_p75_value


# Ensure central estimate is represented in the range.
# If it falls outside, expand the displayed range
# rather than hiding the disagreement.

range_low = min(
    range_low,
    hybrid_value
)

range_high = max(
    range_high,
    hybrid_value
)


# =========================================================
# ASKING PRICE ANALYSIS
# =========================================================

asking_vs_hybrid_pct = (
    (
        target_asking_price
        - hybrid_value
    )
    / hybrid_value
) * 100


asking_vs_comparable_pct = (
    (
        target_asking_price
        - comparable_value
    )
    / comparable_value
) * 100


asking_vs_locality_pct = (
    (
        target_asking_price
        - locality_value
    )
    / locality_value
) * 100


asking_vs_ml_pct = (
    (
        target_asking_price
        - ml_value
    )
    / ml_value
) * 100


# =========================================================
# MARKET POSITION
# =========================================================

target_ppsf = (
    target_asking_price
    / target_area
)


locality_median_ppsf = float(
    locality_summary[
        "locality_statistics"
    ]["median_ppsf"]
)


target_vs_locality_median_pct = (
    (
        target_ppsf
        - locality_median_ppsf
    )
    / locality_median_ppsf
) * 100


# =========================================================
# EVIDENCE STRENGTH
# =========================================================

# Comparable evidence
if same_locality_count >= 5:

    comparable_strength = "STRONG"

elif same_locality_count >= 3:

    comparable_strength = "MODERATE"

else:

    comparable_strength = "LIMITED"


# Locality evidence
if locality_property_count >= 10:

    locality_strength = "STRONG"

elif locality_property_count >= 5:

    locality_strength = "MODERATE"

else:

    locality_strength = "LIMITED"


# Overall evidence
if (
    comparable_strength == "STRONG"
    and locality_strength == "STRONG"
    and agreement_level in [
        "STRONG",
        "MODERATE",
    ]
):

    overall_evidence = "STRONG"

elif (
    comparable_strength in [
        "STRONG",
        "MODERATE",
    ]
    and locality_strength in [
        "STRONG",
        "MODERATE",
    ]
):

    overall_evidence = "MODERATE"

else:

    overall_evidence = "LIMITED"


# =========================================================
# PRINT AGREEMENT
# =========================================================

print("\n" + "=" * 90)
print("EVIDENCE AGREEMENT")
print("=" * 90)

print(
    f"Comparable vs locality : "
    f"{comparable_locality_diff_pct:.2f}%"
)

print(
    f"Comparable vs ML       : "
    f"{comparable_ml_diff_pct:.2f}%"
)

print(
    f"Locality vs ML         : "
    f"{locality_ml_diff_pct:.2f}%"
)

print(
    f"Overall signal spread  : "
    f"{signal_spread_pct:.2f}%"
)

print(
    f"Agreement level        : "
    f"{agreement_level}"
)


# =========================================================
# PRINT HYBRID VALUATION
# =========================================================

print("\n" + "=" * 90)
print("HYBRID VALUATION")
print("=" * 90)

print(
    f"Comparable contribution "
    f"({COMPARABLE_WEIGHT:.0%}) : "
    f"₹{COMPARABLE_WEIGHT * comparable_value:,.0f}"
)

print(
    f"Locality contribution "
    f"({LOCALITY_WEIGHT:.0%}) : "
    f"₹{LOCALITY_WEIGHT * locality_value:,.0f}"
)

print(
    f"ML contribution "
    f"({ML_WEIGHT:.0%}) : "
    f"₹{ML_WEIGHT * ml_value:,.0f}"
)

print(
    f"\nHybrid central estimate : "
    f"₹{hybrid_value:,.0f}"
)

print(
    f"Hybrid ₹/sqft          : "
    f"₹{hybrid_ppsf:,.0f}"
)

print(
    f"\nEvidence range low     : "
    f"₹{range_low:,.0f}"
)

print(
    f"Evidence range high    : "
    f"₹{range_high:,.0f}"
)


# =========================================================
# ASKING PRICE ANALYSIS
# =========================================================

print("\n" + "=" * 90)
print("ASKING PRICE ANALYSIS")
print("=" * 90)

print(
    f"Current asking price       : "
    f"₹{target_asking_price:,.0f}"
)

print(
    f"Current asking ₹/sqft      : "
    f"₹{target_ppsf:,.0f}"
)

print(
    f"Vs hybrid estimate         : "
    f"{asking_vs_hybrid_pct:+.2f}%"
)

print(
    f"Vs comparable valuation   : "
    f"{asking_vs_comparable_pct:+.2f}%"
)

print(
    f"Vs 3-BHK locality value   : "
    f"{asking_vs_locality_pct:+.2f}%"
)

print(
    f"Vs ML valuation            : "
    f"{asking_vs_ml_pct:+.2f}%"
)

print(
    f"Vs locality median ₹/sqft : "
    f"{target_vs_locality_median_pct:+.2f}%"
)


# =========================================================
# EVIDENCE QUALITY
# =========================================================

print("\n" + "=" * 90)
print("EVIDENCE QUALITY")
print("=" * 90)

print(
    f"Comparable evidence : "
    f"{comparable_strength}"
)

print(
    f"Locality evidence   : "
    f"{locality_strength}"
)

print(
    f"Overall evidence    : "
    f"{overall_evidence}"
)


# =========================================================
# EXPLANATION
# =========================================================

print("\n" + "=" * 90)
print("INTERPRETATION")
print("=" * 90)

print(
    "The hybrid estimate combines comparable, "
    "locality and ML evidence."
)

print(
    "The current asking price is compared against "
    "each evidence source rather than being "
    "automatically classified as fair or unfair."
)

print(
    "The evidence range is based primarily on the "
    "observed comparable-market distribution."
)

print(
    "This is an asking-price-based valuation signal, "
    "not a verified transaction-price valuation."
)


# =========================================================
# SAVE RESULT
# =========================================================

result = {

    "target_property_id":
        TARGET_PROPERTY_ID,

    "target_city":
        target_city,

    "target_locality":
        target_locality,

    "target_area_sqft":
        target_area,

    "current_asking_price":
        target_asking_price,

    "signals": {

        "comparable_value":
            comparable_value,

        "locality_value":
            locality_value,

        "ml_value":
            ml_value,
    },

    "weights": {

        "comparable":
            COMPARABLE_WEIGHT,

        "locality":
            LOCALITY_WEIGHT,

        "ml":
            ML_WEIGHT,
    },

    "hybrid": {

        "central_estimate":
            float(hybrid_value),

        "ppsf":
            float(hybrid_ppsf),

        "range_low":
            float(range_low),

        "range_high":
            float(range_high),
    },

    "agreement": {

        "comparable_locality_diff_pct":
            float(comparable_locality_diff_pct),

        "comparable_ml_diff_pct":
            float(comparable_ml_diff_pct),

        "locality_ml_diff_pct":
            float(locality_ml_diff_pct),

        "signal_spread_pct":
            float(signal_spread_pct),

        "agreement_level":
            agreement_level,
    },

    "asking_price_analysis": {

        "asking_vs_hybrid_pct":
            float(asking_vs_hybrid_pct),

        "asking_vs_comparable_pct":
            float(asking_vs_comparable_pct),

        "asking_vs_locality_pct":
            float(asking_vs_locality_pct),

        "asking_vs_ml_pct":
            float(asking_vs_ml_pct),

        "asking_vs_locality_median_ppsf_pct":
            float(
                target_vs_locality_median_pct
            ),
    },

    "evidence": {

        "comparable_strength":
            comparable_strength,

        "locality_strength":
            locality_strength,

        "overall_strength":
            overall_evidence,
    },

    "note":
        "Asking-price-based valuation signal; "
        "not a verified transaction-price valuation.",
}


output_path = (
    OUTPUT_DIR
    / "hybrid_valuation_result.json"
)


with open(
    output_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        result,
        f,
        indent=4
    )


print("\n" + "=" * 90)
print("FILE CREATED")
print("=" * 90)

print(output_path)

print(
    "\nHybrid valuation completed."
)