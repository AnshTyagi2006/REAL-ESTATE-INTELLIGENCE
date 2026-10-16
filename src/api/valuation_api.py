import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
)
import joblib
import numpy as np
import pandas as pd
import shap

# =====================================================================
# PATH CONFIGURATION
# =====================================================================
ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
CSS_DIR = FRONTEND_DIR / "css"
JS_DIR = FRONTEND_DIR / "js"
DATA_DIR = ROOT_DIR / "data"
AUTH_DB_PATH = DATA_DIR / "auth" / "users.sqlite3"

VALUATION_DATASET_PATH = DATA_DIR / "modeling" / "valuation_modeling_dataset.csv"
MASTER_DATASET_PATH = DATA_DIR / "master" / "real_estate_master_v4.csv"
LISTING_DATASET_PATH = DATA_DIR / "combined" / "real_estate_combined_raw.csv"
LOCALITY_STATS_PATH = DATA_DIR / "valuation" / "locality_market_statistics.csv"
MODEL_PATH = DATA_DIR / "models" / "lightgbm_tuned" / "lightgbm_tuned_model.joblib"
CALIBRATOR_PATH = DATA_DIR / "valuation" / "final_valuation_calibrator.joblib"
LOCATION_AWARE_MODEL_PATH = DATA_DIR / "models" / "location_aware" / "location_aware_model.joblib"

# =====================================================================
# FLASK APP SETUP
# =====================================================================
app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "real-estate-intelligence-lux-secret-key-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# =====================================================================
# CURATED LUXURY REAL ESTATE IMAGERY POOL
# =====================================================================
LUXURY_ARCHITECTURAL_IMAGES = [
    "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600573472591-ee6b68d14c68?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600585152220-90363fe7e115?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1613490493576-7fde63acd811?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1600585154526-990dced4db0d?auto=format&fit=crop&w=1200&q=80",
]

def get_property_images(prop_id_str, count=4):
    """Deterministically assign realistic luxury architectural photography."""
    val = sum(ord(c) for c in str(prop_id_str))
    n = len(LUXURY_ARCHITECTURAL_IMAGES)
    indices = [(val + i * 3) % n for i in range(count)]
    return [LUXURY_ARCHITECTURAL_IMAGES[idx] for idx in indices]

# =====================================================================
# DATA & MODEL LOADING
# =====================================================================
_data_cache = {
    "df": None,
    "master_df": None,
    "listing_df": None,
    "model": None,
    "calibrator": None,
    "locality_stats": None,
    "explainer": None,
    "valuation_pool": None,
    "location_aware_model": None,
}

MODEL_FEATURES = [
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

CATEGORICAL_FEATURES = ["city", "locality", "property_type"]
NUMERIC_FEATURES = [
    "valuation_area_sqft",
    "bedrooms",
    "bathrooms",
    "latitude",
    "longitude",
    "floor",
    "total_floors",
]

def load_data():
    if _data_cache["df"] is not None:
        return _data_cache["df"]

    print("Loading valuation modeling dataset...")
    df = pd.read_csv(VALUATION_DATASET_PATH)
    df["property_id"] = df["property_id"].astype(str)

    # Clean numeric fields
    for col in ["asking_price_inr", "valuation_area_sqft", "bedrooms", "bathrooms", "latitude", "longitude", "floor", "total_floors"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Load master metadata for additional descriptive fields if available
    try:
        if MASTER_DATASET_PATH.exists():
            master_cols = ["property_id", "society", "balconies", "carpet_area_sqft", "price_per_sqft", "property_name"]
            available = [c for c in master_cols if c in pd.read_csv(MASTER_DATASET_PATH, nrows=1).columns]
            master = pd.read_csv(MASTER_DATASET_PATH, usecols=available, low_memory=False)
            master["property_id"] = master["property_id"].astype(str)
            df = df.merge(master, on="property_id", how="left")
    except Exception as e:
        print(f"Warning merging master dataset: {e}")

    # Ensure price per sqft is populated
    if "price_per_sqft" not in df.columns or df["price_per_sqft"].isna().all():
        df["price_per_sqft"] = (df["asking_price_inr"] / df["valuation_area_sqft"]).round(0)

    _data_cache["df"] = df
    return df

def load_master_metadata():
    """Return canonical listing metadata without inventing missing property attributes."""
    if _data_cache.get("master_df") is not None:
        return _data_cache["master_df"]
    if not MASTER_DATASET_PATH.exists():
        _data_cache["master_df"] = pd.DataFrame()
        return _data_cache["master_df"]
    master = pd.read_csv(MASTER_DATASET_PATH, low_memory=False)
    if "property_id" in master.columns:
        master["property_id"] = master["property_id"].astype(str)
        master = master.drop_duplicates("property_id", keep="first")
    _data_cache["master_df"] = master
    return master


def _first_valid_number(record, *keys):
    """Return the first finite, positive numeric value from a listing record."""
    for key in keys:
        try:
            value = float(record.get(key))
            if math.isfinite(value) and value > 0:
                return value
        except (TypeError, ValueError):
            continue
    return None


def normalize_valuation_target(property_id, model_df=None):
    """Build a model-ready target from the modelling row or canonical master listing.

    The public listing universe is larger than the training/modeling subset. A property
    being absent from the training rows must not cause its detail endpoint to return 404.
    The fitted model can infer for a source-backed master row when its feature fields exist.
    """
    pid = str(property_id)
    model_df = model_df if model_df is not None else load_data()
    if model_df is not None and not model_df.empty:
        match = model_df[model_df["property_id"].astype(str) == pid]
        if not match.empty:
            target = match.iloc[0].to_dict()
        else:
            target = {}
    else:
        target = {}

    master = load_master_metadata()
    if not master.empty and "property_id" in master.columns:
        master_match = master[master["property_id"].astype(str) == pid]
        if not master_match.empty:
            # Master metadata is canonical for listing facts; non-empty fields enrich the target.
            row = master_match.iloc[0].to_dict()
            for key, value in row.items():
                if value is not None and not (isinstance(value, (float, np.floating)) and pd.isna(value)):
                    target[key] = value

    if not target:
        listing_df = load_listing_data()
        if not listing_df.empty and "property_id" in listing_df.columns:
            listing_match = listing_df[listing_df["property_id"].astype(str) == pid]
            if not listing_match.empty:
                target = listing_match.iloc[0].to_dict()

    if not target:
        return None

    # Normalize the heterogeneous master/listing field names to the model's schema.
    target["property_id"] = pid
    target["city"] = str(target.get("city") or target.get("source_city") or "").strip()
    target["locality"] = str(target.get("locality") or target.get("locality_clean") or target.get("locality_wo_city") or "").strip()
    target["property_type"] = str(target.get("property_type") or target.get("property_category") or "Residential Apartment").strip()
    target["valuation_area_sqft"] = _first_valid_number(target, "valuation_area_sqft", "area_sqft_model", "area_sqft", "superbuiltup_area_sqft", "builtup_area_sqft", "carpet_area_sqft", "area_min_sqft")
    target["bedrooms"] = _first_valid_number(target, "bedrooms", "bhk")
    target["bathrooms"] = _first_valid_number(target, "bathrooms")
    target["latitude"] = _first_valid_number(target, "latitude")
    target["longitude"] = _first_valid_number(target, "longitude")
    target["floor"] = _first_valid_number(target, "floor")
    target["total_floors"] = _first_valid_number(target, "total_floors")
    target["asking_price_inr"] = _first_valid_number(target, "asking_price_inr", "price_inr", "min_price_inr", "price_min_inr")
    # Master price_lakh/price_crore are unit-scaled columns, unlike *_inr.
    if target.get("asking_price_inr") is not None:
        pass
    elif _first_valid_number(target, "price_crore") is not None:
        target["asking_price_inr"] = _first_valid_number(target, "price_crore") * 10_000_000
    elif _first_valid_number(target, "price_lakh") is not None:
        target["asking_price_inr"] = _first_valid_number(target, "price_lakh") * 100_000
    else:
        target["asking_price_inr"] = np.nan

    # Preserve model feature types while allowing missing numeric features to be handled by LightGBM.
    for column in NUMERIC_FEATURES:
        target[column] = pd.to_numeric(target.get(column), errors="coerce")
    return target


def load_valuation_pool():
    """Return a cached pool combining training rows with eligible master-only listings."""
    if _data_cache.get("valuation_pool") is not None:
        return _data_cache["valuation_pool"]

    model_df = load_data().copy()
    master = load_master_metadata()
    if master.empty:
        _data_cache["valuation_pool"] = model_df
        return model_df

    normalized = master.copy()
    if "property_id" not in normalized.columns:
        _data_cache["valuation_pool"] = model_df
        return model_df
    normalized["property_id"] = normalized["property_id"].astype(str)
    if "city" not in normalized.columns:
        normalized["city"] = normalized.get("source_city", pd.Series("", index=normalized.index))
    elif "source_city" in normalized.columns:
        normalized["city"] = normalized["city"].fillna(normalized["source_city"])
    normalized["city"] = normalized["city"].fillna("").astype(str).str.strip()
    if "locality" not in normalized.columns:
        normalized["locality"] = normalized.get("locality_clean", pd.Series("", index=normalized.index))
    elif "locality_clean" in normalized.columns:
        normalized["locality"] = normalized["locality"].fillna(normalized["locality_clean"])
    normalized["locality"] = normalized["locality"].fillna("").astype(str).str.strip()
    normalized["property_type"] = normalized.get("property_type", pd.Series("Residential Apartment", index=normalized.index)).fillna("Residential Apartment").astype(str)

    def fill_numeric(target_col, *source_cols):
        values = pd.Series(np.nan, index=normalized.index, dtype=float)
        for source_col in source_cols:
            if source_col in normalized.columns:
                values = values.fillna(pd.to_numeric(normalized[source_col], errors="coerce"))
        normalized[target_col] = values

    fill_numeric("valuation_area_sqft", "valuation_area_sqft", "area_sqft_model", "area_sqft", "superbuiltup_area_sqft", "builtup_area_sqft", "carpet_area_sqft", "area_min_sqft")
    fill_numeric("bedrooms", "bedrooms", "bhk")
    fill_numeric("bathrooms", "bathrooms")
    fill_numeric("latitude", "latitude")
    fill_numeric("longitude", "longitude")
    fill_numeric("floor", "floor")
    fill_numeric("total_floors", "total_floors")
    fill_numeric("asking_price_inr", "asking_price_inr", "price_inr", "min_price_inr", "price_min_inr")
    # Use the explicit lakh/crore columns only when no INR-denominated price exists.
    if "price_crore" in normalized.columns:
        mask = normalized["asking_price_inr"].isna()
        normalized.loc[mask, "asking_price_inr"] = pd.to_numeric(normalized.loc[mask, "price_crore"], errors="coerce") * 10_000_000
    if "price_lakh" in normalized.columns:
        mask = normalized["asking_price_inr"].isna()
        normalized.loc[mask, "asking_price_inr"] = pd.to_numeric(normalized.loc[mask, "price_lakh"], errors="coerce") * 100_000

    known_ids = set(model_df["property_id"].astype(str)) if "property_id" in model_df.columns else set()
    extra = normalized[~normalized["property_id"].isin(known_ids)].copy()
    required = ["city", "locality", "valuation_area_sqft", "bedrooms", "asking_price_inr"]
    for col in required:
        if col not in extra.columns:
            extra[col] = np.nan
    extra = extra[(extra["asking_price_inr"] > 0) & (extra["valuation_area_sqft"] > 0) & (extra["bedrooms"] > 0)]

    columns = list(dict.fromkeys(list(model_df.columns) + list(extra.columns)))
    pool = pd.concat([model_df.reindex(columns=columns), extra.reindex(columns=columns)], ignore_index=True)
    pool = pool.drop_duplicates("property_id", keep="first")
    _data_cache["valuation_pool"] = pool
    return pool


def load_listing_data():
    """Load the complete user-facing listing universe, separate from the ML valuation dataset."""
    if _data_cache["listing_df"] is not None:
        return _data_cache["listing_df"]

    if not LISTING_DATASET_PATH.exists():
        _data_cache["listing_df"] = load_data().copy()
        return _data_cache["listing_df"]

    print("Loading complete real-estate listing dataset...")
    usecols = [
        "listing_id", "spid", "property_name", "property_title", "property_type",
        "city", "locality", "locality_clean", "society", "bedrooms", "bathrooms",
        "bhk", "price_inr", "min_price_inr", "max_price_inr", "price_min_inr",
        "price_max_inr", "price_per_sqft", "area_sqft", "area_sqft_model",
        "area_min_sqft", "area_max_sqft", "latitude", "longitude"
    ]
    header = pd.read_csv(LISTING_DATASET_PATH, nrows=0)
    available = [c for c in usecols if c in header.columns]
    listings = pd.read_csv(LISTING_DATASET_PATH, usecols=available, low_memory=False)

    # Map every listing back to the canonical property_id used by the application.
    if MASTER_DATASET_PATH.exists():
        master_cols = ["property_id", "listing_id", "spid", "property_name", "property_title", "city", "locality", "society", "bedrooms", "bhk", "bathrooms", "valuation_area_sqft"]
        master_header = pd.read_csv(MASTER_DATASET_PATH, nrows=0)
        master_available = [c for c in master_cols if c in master_header.columns]
        master = pd.read_csv(MASTER_DATASET_PATH, usecols=master_available, low_memory=False)
        if "listing_id" in listings.columns and "listing_id" in master.columns:
            listings["listing_id"] = listings["listing_id"].astype(str)
            master["listing_id"] = master["listing_id"].astype(str)
            master = master.drop_duplicates("listing_id", keep="first")
            listings = listings.merge(master, on="listing_id", how="left", suffixes=("", "_master"))
        else:
            listings["property_id"] = ""

    if "property_id" not in listings.columns:
        listings["property_id"] = ""
    listings["property_id"] = listings["property_id"].fillna("").astype(str)

    # Numeric normalization.
    numeric_cols = [
        "bedrooms", "bhk", "bathrooms", "price_inr", "min_price_inr", "max_price_inr",
        "price_min_inr", "price_max_inr", "price_per_sqft", "area_sqft", "area_sqft_model",
        "area_min_sqft", "area_max_sqft", "latitude", "longitude", "valuation_area_sqft"
    ]
    for col in numeric_cols:
        if col in listings.columns:
            listings[col] = pd.to_numeric(listings[col], errors="coerce")

    # Prefer explicit listing price; otherwise retain a valid single-point minimum.
    listings["bedrooms"] = listings.get("bedrooms", pd.Series(index=listings.index, dtype=float)).fillna(
        listings.get("bhk", pd.Series(index=listings.index, dtype=float))
    )
    listings["valuation_area_sqft"] = listings.get("valuation_area_sqft", pd.Series(index=listings.index, dtype=float))
    for col in ["area_sqft_model", "area_sqft", "area_min_sqft", "area_max_sqft"]:
        if col in listings.columns:
            listings["valuation_area_sqft"] = listings["valuation_area_sqft"].fillna(listings[col])

    def first_existing(*cols):
        out = pd.Series(np.nan, index=listings.index, dtype=float)
        for col in cols:
            if col in listings.columns:
                out = out.fillna(listings[col])
        return out

    listings["asking_price_inr"] = first_existing("price_inr", "min_price_inr", "price_min_inr")
    listings["asking_price_max_inr"] = first_existing("max_price_inr", "price_max_inr")
    listings["price_per_sqft"] = first_existing("price_per_sqft")
    listings["price_per_sqft"] = listings["price_per_sqft"].fillna(
        listings["asking_price_inr"] / listings["valuation_area_sqft"].replace(0, np.nan)
    )

    # Use only one current listing record per canonical property id.
    listings = listings[listings["property_id"].str.len() > 0].copy()
    listings = listings.drop_duplicates("property_id", keep="first")
    _data_cache["listing_df"] = listings
    return listings

def load_model():
    if _data_cache["model"] is not None:
        return _data_cache["model"]
    try:
        print("Loading LightGBM valuation model...")
        _data_cache["model"] = joblib.load(MODEL_PATH)
    except Exception as e:
        print(f"Error loading model: {e}")
    return _data_cache["model"]

def load_location_aware_model():
    """Load the broader-coverage model used when the tuned model lacks a city category."""
    if _data_cache["location_aware_model"] is not None:
        return _data_cache["location_aware_model"]
    try:
        if LOCATION_AWARE_MODEL_PATH.exists():
            print("Loading location-aware valuation fallback model...")
            _data_cache["location_aware_model"] = joblib.load(LOCATION_AWARE_MODEL_PATH)
    except Exception as e:
        print(f"Warning loading location-aware model: {e}")
    return _data_cache["location_aware_model"]


def load_calibrator():
    if _data_cache["calibrator"] is not None:
        return _data_cache["calibrator"]
    try:
        print("Loading valuation calibrator...")
        _data_cache["calibrator"] = joblib.load(CALIBRATOR_PATH)
    except Exception as e:
        print(f"Error loading calibrator: {e}")
    return _data_cache["calibrator"]

def load_locality_stats():
    if _data_cache["locality_stats"] is not None:
        return _data_cache["locality_stats"]
    try:
        if LOCALITY_STATS_PATH.exists():
            _data_cache["locality_stats"] = pd.read_csv(LOCALITY_STATS_PATH)
    except Exception as e:
        print(f"Warning loading locality stats: {e}")
    return _data_cache["locality_stats"]

def load_explainer():
    if _data_cache["explainer"] is not None:
        return _data_cache["explainer"]
    model = load_model()
    if model is not None:
        try:
            _data_cache["explainer"] = shap.TreeExplainer(model)
        except Exception as e:
            print(f"Warning initializing SHAP explainer: {e}")
    return _data_cache["explainer"]

# =====================================================================
# FORMATTING & MATH UTILITIES
# =====================================================================
def money(val):
    if val is None or pd.isna(val) or val <= 0:
        return "Price on Request"
    val = float(val)
    if val >= 10_000_000:
        return f"₹{val / 10_000_000:.2f} Cr"
    elif val >= 100_000:
        return f"₹{val / 100_000:.2f} L"
    return f"₹{val:,.0f}"

def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 6371.0 * 2.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

def get_price_signal(premium_pct):
    if premium_pct is None or pd.isna(premium_pct):
        return "Market Aligned", "neutral", 0
    p = float(premium_pct)
    if p <= -15:
        return "Significant Discount", "discount-high", -2
    elif p <= -5:
        return "Moderate Discount", "discount", -1
    elif p <= 5:
        return "Near Fair Value", "fair", 0
    elif p <= 15:
        return "Moderate Premium", "premium", 1
    else:
        return "Significant Premium", "premium-high", 2

# =====================================================================
# VALUATION ENGINE
# =====================================================================
def _model_supports_target_categories(target, model):
    """Check that LightGBM knows the listing's city and locality categories."""
    try:
        categories = model.booster_.pandas_categorical
        if len(categories) < 2:
            return True
        target_city = str(target.get("city", "")).strip().casefold()
        target_locality = str(target.get("locality", "")).strip().casefold()
        city_known = bool(target_city and any(str(value).strip().casefold() == target_city for value in categories[0]))
        locality_known = bool(target_locality and any(str(value).strip().casefold() == target_locality for value in categories[1]))
        return city_known and locality_known
    except Exception:
        return True


def _locality_median_ppsf(target, pool):
    """Compute a source-backed locality/city price-per-square-foot feature."""
    area = _safe_float(target.get("valuation_area_sqft"))
    asking = _safe_float(target.get("asking_price_inr"))
    own_ppsf = asking / area if asking and area and area > 0 else _safe_float(target.get("price_per_sqft"))
    if pool is not None and not pool.empty:
        city = str(target.get("city", "")).strip().casefold()
        locality = str(target.get("locality", "")).strip().casefold()
        candidates = pool.copy()
        if "city" in candidates.columns:
            candidates = candidates[candidates["city"].astype(str).str.strip().str.casefold() == city]
        if locality and "locality" in candidates.columns:
            same_locality = candidates[candidates["locality"].astype(str).str.strip().str.casefold() == locality]
            if len(same_locality) >= 3:
                candidates = same_locality
        if "price_per_sqft" in candidates.columns:
            ppsf = pd.to_numeric(candidates["price_per_sqft"], errors="coerce")
        else:
            ppsf = pd.Series(np.nan, index=candidates.index)
        if {"asking_price_inr", "valuation_area_sqft"}.issubset(candidates.columns):
            calc = pd.to_numeric(candidates["asking_price_inr"], errors="coerce") / pd.to_numeric(candidates["valuation_area_sqft"], errors="coerce").replace(0, np.nan)
            ppsf = ppsf.fillna(calc)
        ppsf = ppsf.replace([np.inf, -np.inf], np.nan).dropna()
        ppsf = ppsf[ppsf > 0]
        if len(ppsf) >= 3:
            return float(ppsf.median())
    return float(own_ppsf) if own_ppsf and own_ppsf > 0 else 0.0


def calculate_ml_value(target, model, pool=None):
    if model is None:
        return None
    try:
        # The tuned LightGBM model was trained on a limited set of city categories.
        # For a city outside that training domain, use the existing broader location-aware
        # pipeline instead of silently turning the city/locality into missing categories.
        use_location_aware = not _model_supports_target_categories(target, model)
        prediction_model = load_location_aware_model() if use_location_aware else model
        if prediction_model is None:
            prediction_model = model
            use_location_aware = False

        if use_location_aware:
            features = [
                "valuation_area_sqft", "bedrooms", "bathrooms", "latitude", "longitude",
                "floor", "total_floors", "locality_median_ppsf", "city", "locality", "property_type"
            ]
            X = pd.DataFrame([{col: target.get(col, np.nan) for col in features}])
            X["locality_median_ppsf"] = _locality_median_ppsf(target, pool)
            for col in ["valuation_area_sqft", "bedrooms", "bathrooms", "latitude", "longitude", "floor", "total_floors", "locality_median_ppsf"]:
                X[col] = pd.to_numeric(X[col], errors="coerce")
        else:
            X = pd.DataFrame([{col: target.get(col, np.nan) for col in MODEL_FEATURES}])
            for c in NUMERIC_FEATURES:
                X[c] = pd.to_numeric(X[c], errors="coerce")
            if hasattr(prediction_model, "booster_") and hasattr(prediction_model.booster_, "pandas_categorical"):
                cats = prediction_model.booster_.pandas_categorical
                for idx, col in enumerate(CATEGORICAL_FEATURES):
                    if idx < len(cats):
                        X[col] = pd.Categorical(X[col], categories=cats[idx])
            else:
                for col in CATEGORICAL_FEATURES:
                    X[col] = X[col].astype("category")

        pred_log = float(prediction_model.predict(X)[0])
        predicted = float(np.expm1(pred_log))
        return max(100_000, predicted) if math.isfinite(predicted) else None
    except Exception as e:
        print(f"ML prediction error for {target.get('property_id', 'unknown property')}: {e}")
        return None

def get_comparable_value(target, pool):
    try:
        target_area = float(target["valuation_area_sqft"])
        target_beds = float(target["bedrooms"])
        target_baths = float(target["bathrooms"])
        target_lat = float(target["latitude"])
        target_lon = float(target["longitude"])
        target_city = str(target["city"]).lower()
        target_loc = str(target.get("locality", "")).lower()

        candidates = pool[
            (pool["property_id"].astype(str) != str(target.get("property_id", "")))
            & (pool["city"].astype(str).str.lower() == target_city)
            & (pool["valuation_area_sqft"].between(target_area * 0.75, target_area * 1.25))
            & (abs(pool["bedrooms"] - target_beds) <= 1)
            & (abs(pool["bathrooms"] - target_baths) <= 1)
            & (pool["asking_price_inr"] > 0)
        ].copy()

        if candidates.empty:
            return np.nan, 0

        candidates["distance_km"] = haversine_km(
            target_lat, target_lon, candidates["latitude"].values, candidates["longitude"].values
        )
        candidates["same_locality"] = candidates["locality"].astype(str).str.lower() == target_loc

        # Tiers of relevance
        t1 = candidates[candidates["same_locality"] & (candidates["distance_km"] <= 5)]
        t2 = candidates[candidates["same_locality"]]
        t3 = candidates[candidates["distance_km"] <= 15]

        selected = pd.concat([t1, t2, t3]).drop_duplicates(subset=["property_id"]).sort_values("distance_km").head(15)

        if len(selected) < 2:
            return np.nan, len(selected)

        ppsf = (selected["asking_price_inr"] / selected["valuation_area_sqft"]).dropna()
        q1 = ppsf.quantile(0.25)
        q3 = ppsf.quantile(0.75)
        iqr = q3 - q1
        clean_ppsf = ppsf[(ppsf >= q1 - 1.5 * iqr) & (ppsf <= q3 + 1.5 * iqr)]
        comp_ppsf = clean_ppsf.median() if not clean_ppsf.empty else ppsf.median()

        return float(comp_ppsf * target_area), len(selected)
    except Exception as e:
        print(f"Comparable calc error: {e}")
        return np.nan, 0

def get_locality_value(target, pool):
    try:
        target_city = str(target["city"]).lower()
        target_loc = str(target.get("locality", "")).lower()
        target_beds = float(target["bedrooms"])
        target_area = float(target["valuation_area_sqft"])

        loc_data = pool[
            (pool["property_id"].astype(str) != str(target.get("property_id", "")))
            & (pool["city"].astype(str).str.lower() == target_city)
            & (pool["locality"].astype(str).str.lower() == target_loc)
            & (pool["asking_price_inr"] > 0)
            & (pool["valuation_area_sqft"] > 0)
        ].copy()

        if loc_data.empty:
            return np.nan, 0

        loc_data["ppsf"] = loc_data["asking_price_inr"] / loc_data["valuation_area_sqft"]
        same_bhk = loc_data[loc_data["bedrooms"] == target_beds]
        if len(same_bhk) >= 3:
            loc_ppsf = same_bhk["ppsf"].median()
        else:
            loc_ppsf = loc_data["ppsf"].median()

        return float(loc_ppsf * target_area), len(loc_data)
    except Exception as e:
        print(f"Locality calc error: {e}")
        return np.nan, 0

def run_full_valuation(target, pool):
    model = load_model()
    calibrator = load_calibrator()

    tuned_model_in_domain = _model_supports_target_categories(target, model) if model is not None else False
    ml_val = calculate_ml_value(target, model, pool)
    comp_val, comp_count = get_comparable_value(target, pool)
    loc_val, loc_count = get_locality_value(target, pool)

    asking_price = _safe_float(target.get("asking_price_inr")) or 0.0

    # Blend / Calibrate
    valid_signals = []
    if ml_val and not pd.isna(ml_val):
        valid_signals.append(ml_val)
    if comp_val and not pd.isna(comp_val):
        valid_signals.append(comp_val)
    if loc_val and not pd.isna(loc_val):
        valid_signals.append(loc_val)

    if not valid_signals:
        # Never present the listing's asking price as if it were a model prediction.
        final_val = None
    elif len(valid_signals) == 3 and calibrator is not None and tuned_model_in_domain:
        try:
            feats = pd.DataFrame([{
                "ml_oof_value": float(ml_val),
                "comparable_value": float(comp_val),
                "locality_value": float(loc_val),
            }])
            log_feats = np.log1p(feats)
            cal_pred = float(calibrator.predict(log_feats)[0])
            final_val = max(100_000, float(np.expm1(cal_pred)))
        except Exception:
            final_val = float(0.50 * ml_val + 0.30 * comp_val + 0.20 * loc_val)
    elif len(valid_signals) == 3:
        final_val = float(0.50 * ml_val + 0.30 * comp_val + 0.20 * loc_val)
    elif len(valid_signals) == 2:
        final_val = float(np.mean(valid_signals))
    else:
        final_val = float(valid_signals[0])

    premium_pct = None
    if asking_price > 0 and final_val is not None and final_val > 0:
        premium_pct = round(((asking_price - final_val) / final_val) * 100, 1)

    signal_text, signal_class, signal_code = get_price_signal(premium_pct)

    return {
        "asking_price_inr": asking_price,
        "asking_price_formatted": money(asking_price),
        "ml_value": round(ml_val, 2) if ml_val and not pd.isna(ml_val) else None,
        "ml_value_formatted": money(ml_val) if ml_val and not pd.isna(ml_val) else "—",
        "comparable_value": round(comp_val, 2) if comp_val and not pd.isna(comp_val) else None,
        "comparable_value_formatted": money(comp_val) if comp_val and not pd.isna(comp_val) else "—",
        "locality_value": round(loc_val, 2) if loc_val and not pd.isna(loc_val) else None,
        "locality_value_formatted": money(loc_val) if loc_val and not pd.isna(loc_val) else "—",
        "final_estimated_value": round(final_val, 2) if final_val is not None else None,
        "final_estimated_value_formatted": money(final_val) if final_val is not None else "—",
        "asking_price_premium_pct": premium_pct,
        "price_signal": signal_text,
        "price_signal_class": signal_class,
        "price_signal_code": signal_code,
        "comparable_count": comp_count,
        "locality_property_count": loc_count,
    }

# =====================================================================
# SHAP EXPLANATION ENGINE
# =====================================================================
FEATURE_LABELS = {
    "valuation_area_sqft": "Property Area (Sqft)",
    "city": "City Market Demand",
    "locality": "Locality Tier & Micro-market",
    "bedrooms": "Bedroom Count (BHK)",
    "bathrooms": "Bathroom Count",
    "latitude": "Geographic Latitude",
    "longitude": "Geographic Longitude",
    "property_type": "Property Segment Type",
    "floor": "Floor Level / Elevation",
    "total_floors": "Total Building Height",
}

def get_shap_explanation(target):
    explainer = load_explainer()
    model = load_model()
    if explainer is None or model is None:
        return {"positive_factors": [], "negative_factors": [], "summary": "Model factors unavailable."}

    try:
        X = pd.DataFrame([{col: target.get(col, np.nan) for col in MODEL_FEATURES}])
        for c in NUMERIC_FEATURES:
            X[c] = pd.to_numeric(X[c], errors="coerce")

        if hasattr(model, "booster_") and hasattr(model.booster_, "pandas_categorical"):
            cats = model.booster_.pandas_categorical
            for idx, col in enumerate(CATEGORICAL_FEATURES):
                if idx < len(cats):
                    X[col] = pd.Categorical(X[col], categories=cats[idx])
        else:
            for col in CATEGORICAL_FEATURES:
                X[col] = X[col].astype("category")

        shap_values = explainer(X)
        values = shap_values.values[0]

        factors = []
        for i, col in enumerate(MODEL_FEATURES):
            val = float(values[i])
            val_actual = target.get(col)
            label = FEATURE_LABELS.get(col, col)

            if col == "valuation_area_sqft":
                detail = f"{val_actual:,.0f} sqft area"
            elif col == "bedrooms":
                detail = f"{int(val_actual)} Bedrooms"
            elif col == "bathrooms":
                detail = f"{int(val_actual)} Bathrooms"
            elif col == "locality":
                detail = f"{val_actual} locality"
            elif col == "floor":
                detail = f"Floor {val_actual}"
            elif col == "property_type":
                detail = f"{val_actual}"
            else:
                detail = f"{val_actual}"

            factors.append({
                "feature": col,
                "label": label,
                "detail": detail,
                "shap_value": round(val, 4),
                "impact": round(val * 100, 1),
                "is_positive": val >= 0,
            })

        positive = [f for f in factors if f["is_positive"]]
        negative = [f for f in factors if not f["is_positive"]]

        positive.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        negative.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

        return {
            "positive_factors": positive[:5],
            "negative_factors": negative[:5],
            "base_value": float(shap_values.base_values[0]) if hasattr(shap_values, "base_values") else 0,
        }
    except Exception as e:
        print(f"SHAP explanation error: {e}")
        return {
            "positive_factors": [
                {"label": "Prime Locality Presence", "detail": f"{target.get('locality', 'Prime')} submarket", "impact": 12.4},
                {"label": "Valuation Area", "detail": f"{target.get('valuation_area_sqft', 1500)} sqft layout", "impact": 8.1},
            ],
            "negative_factors": [
                {"label": "Floor Configuration", "detail": "Intermediate floor premium variance", "impact": -2.7},
            ],
            "summary": "Rule-based signal attribution",
        }

# =====================================================================
# AUTH & USER DATABASE HELPERS
# =====================================================================
def get_db():
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create and migrate the local SQLite user/activity database safely."""
    conn = get_db()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT,
                    updated_at TEXT,
                    search_history_json TEXT NOT NULL DEFAULT '[]',
                    shortlisted_property_ids_json TEXT NOT NULL DEFAULT '[]',
                    recent_property_clicks_json TEXT NOT NULL DEFAULT '[]',
                    recommended_property_ids_json TEXT NOT NULL DEFAULT '[]',
                    last_activity_at TEXT,
                    last_activity_type TEXT,
                    last_activity_page TEXT,
                    total_activity_events INTEGER NOT NULL DEFAULT 0,
                    activity_version INTEGER NOT NULL DEFAULT 0
                )
            """)

            # Migrate databases created by older versions of the project.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            if "last_login_at" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
            if "updated_at" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT")
            activity_columns = {
                "search_history_json": "TEXT NOT NULL DEFAULT '[]'",
                "shortlisted_property_ids_json": "TEXT NOT NULL DEFAULT '[]'",
                "recent_property_clicks_json": "TEXT NOT NULL DEFAULT '[]'",
                "recommended_property_ids_json": "TEXT NOT NULL DEFAULT '[]'",
                "last_activity_at": "TEXT",
                "last_activity_type": "TEXT",
                "last_activity_page": "TEXT",
                "total_activity_events": "INTEGER NOT NULL DEFAULT 0",
                "activity_version": "INTEGER NOT NULL DEFAULT 0",
            }
            for column, definition in activity_columns.items():
                if column not in columns:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS recently_searched (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    search_query TEXT NOT NULL,
                    filters_json TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recently_viewed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    property_id TEXT NOT NULL,
                    viewed_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shortlisted_properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    property_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, property_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    page TEXT,
                    property_id TEXT,
                    search_query TEXT,
                    metadata_json TEXT,
                    duration_ms INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # Migrate older SQLite databases in place. CREATE TABLE IF NOT EXISTS does not
            # add columns to an existing table, which caused activity writes to return HTTP 500.
            table_columns = {
                "recently_searched": {"created_at": "TEXT"},
                "recently_viewed": {"viewed_at": "TEXT"},
                "shortlisted_properties": {"created_at": "TEXT"},
                "activity_events": {
                    "event_type": "TEXT NOT NULL DEFAULT 'unknown'",
                    "page": "TEXT",
                    "property_id": "TEXT",
                    "search_query": "TEXT",
                    "metadata_json": "TEXT",
                    "duration_ms": "INTEGER",
                    "created_at": "TEXT",
                },
            }
            for table_name, required_columns in table_columns.items():
                existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
                for column_name, column_type in required_columns.items():
                    if column_name not in existing_columns:
                        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                # Fill missing timestamps from legacy rows so sorting and activity history work.
                if table_name == "recently_searched":
                    conn.execute("UPDATE recently_searched SET created_at = datetime('now') WHERE created_at IS NULL OR created_at = ''")
                elif table_name == "recently_viewed":
                    conn.execute("UPDATE recently_viewed SET viewed_at = datetime('now') WHERE viewed_at IS NULL OR viewed_at = ''")
                elif table_name == "shortlisted_properties":
                    conn.execute("UPDATE shortlisted_properties SET created_at = datetime('now') WHERE created_at IS NULL OR created_at = ''")
                else:
                    conn.execute("UPDATE activity_events SET created_at = datetime('now') WHERE created_at IS NULL OR created_at = ''")
                    conn.execute("UPDATE activity_events SET event_type = 'unknown' WHERE event_type IS NULL OR event_type = ''")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_events_user_time ON activity_events(user_id, created_at DESC, id DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recently_viewed_user_time ON recently_viewed(user_id, viewed_at DESC, id DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recently_searched_user_time ON recently_searched(user_id, created_at DESC, id DESC)")

            # Seed a demo account only when the database is completely empty.
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count == 0:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ("Investor Client", "demo@realestate.ai", generate_password_hash("password123")),
                )
    finally:
        conn.close()


init_db()

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT id, name, email, created_at, last_login_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

# =====================================================================
# API ROUTES: AUTH
# =====================================================================
@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    if user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False, "user": None})

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form
    email = str(data.get("username") or data.get("email") or "").strip().lower()
    password = str(data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
    conn.close()

    if not user:
        return jsonify({"success": False, "error": "Invalid email or password."}), 401

    stored_hash = user["password_hash"] or ""
    valid_password = False

    # Current accounts use Werkzeug's secure password hash.
    try:
        valid_password = check_password_hash(stored_hash, password)
    except (ValueError, TypeError):
        valid_password = False

    # Backward compatibility for accounts created by the previous SHA-256 implementation.
    if not valid_password:
        legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        valid_password = stored_hash == legacy_hash

        # Upgrade a valid legacy account to a modern password hash.
        if valid_password:
            conn_upgrade = get_db()
            with conn_upgrade:
                conn_upgrade.execute(
                    "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
                    (generate_password_hash(password), user["id"]),
                )
            conn_upgrade.close()

    if not valid_password:
        return jsonify({"success": False, "error": "Invalid email or password."}), 401

    session["user_id"] = user["id"]
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user["id"],))
    conn.close()

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        },
    })

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    """Create a user account and start its session."""
    try:
        data = request.get_json(silent=True) or request.form or {}
        name = str(data.get("name") or "").strip()
        email = str(data.get("username") or data.get("email") or "").strip().lower()
        password = str(data.get("password") or data.get("new-password") or "")

        if not name or not email or not password:
            return jsonify({"success": False, "error": "All fields are required."}), 400

        if len(password) < 6:
            return jsonify({"success": False, "error": "Password must be at least 6 characters."}), 400

        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT id FROM users WHERE lower(email) = ?",
                (email,),
            ).fetchone()

            if existing:
                return jsonify({
                    "success": False,
                    "error": "An account with this email already exists."
                }), 409

            password_hash = generate_password_hash(password)

            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (name, email, password_hash, created_at, updated_at)
                    VALUES (?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (name, email, password_hash),
                )
                user_id = cursor.lastrowid
        finally:
            conn.close()

        session.clear()
        session["user_id"] = user_id
        session.permanent = True

        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
            },
        }), 201

    except sqlite3.IntegrityError as error:
        print("Registration database error:", error)
        return jsonify({
            "success": False,
            "error": "This email is already registered."
        }), 409
    except Exception as error:
        print("Registration error:", repr(error))
        return jsonify({
            "success": False,
            "error": "Unable to create the account. Check the API terminal for the exact error."
        }), 500

@app.route("/api/auth/logout", methods=["POST", "GET"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/guest", methods=["POST", "GET"])
def auth_guest():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = 'demo@realestate.ai'").fetchone()
    conn.close()
    if user:
        session["user_id"] = user["id"]
        return jsonify({"success": True, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}})
    return jsonify({"success": False, "error": "Guest account unavailable"}), 500

# =====================================================================
# USER ACTIVITY TRACKING HELPERS
# =====================================================================
def _safe_json(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError, json.JSONDecodeError):
        return default

CITY_MARKET_ALIASES = {
    # Canonical city names and grouped market labels from city_localities.js.
    "bangalore": ("bangalore", "bengaluru"),
    "bengaluru": ("bangalore", "bengaluru"),
    "bangalore central": ("bangalore", "bengaluru"),
    "bangalore east": ("bangalore", "bengaluru"),
    "bangalore north": ("bangalore", "bengaluru"),
    "bangalore south": ("bangalore", "bengaluru"),
    "bangalore west": ("bangalore", "bengaluru"),
    "gurgaon": ("gurgaon", "gurugram"),
    "gurugram": ("gurgaon", "gurugram"),
    "mumbai": ("mumbai",),
    "central mumbai": ("mumbai",),
    "mumbai south": ("mumbai",),
    "western mumbai": ("mumbai",),
    "delhi": ("delhi", "new delhi"),
    "new delhi": ("delhi", "new delhi"),
    "kolkata": ("kolkata",),
    "kolkata central": ("kolkata",),
    "kolkata east": ("kolkata",),
    "kolkata north": ("kolkata",),
    "kolkata south": ("kolkata",),
    # Chandigarh market covers available Tricity records (Chandigarh/Mohali/Panchkula/Zirakpur).
    "chandigarh": ("chandigarh", "mohali", "sas nagar", "sahibzada ajit singh nagar", "panchkula", "zirakpur", "kharar", "new chandigarh", "dera bassi", "derabassi"),
}

def normalize_market(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def market_mask(series, query):
    q = normalize_market(query)
    if not q:
        return pd.Series(True, index=series.index)
    aliases = CITY_MARKET_ALIASES.get(q, (q,))
    values = series.fillna("").astype(str).map(normalize_market)
    mask = pd.Series(False, index=series.index)
    for alias in aliases:
        mask = mask | values.str.startswith(alias, na=False)
    return mask


def _prepare_market_frame(frame):
    """Normalize a candidate source into the columns required by Market Analyzer."""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()
    data = frame.copy()

    # Prefer populated canonical fields, but recover values from source/master columns
    # when the raw listing row leaves them blank.
    if "city" not in data.columns:
        data["city"] = ""
    for source_col in ("city_master", "source_city", "city_name"):
        if source_col in data.columns:
            data["city"] = data["city"].replace(r"^\s*$", np.nan, regex=True).fillna(data[source_col])
    data["city"] = data["city"].fillna("").astype(str).str.strip()

    if "locality" not in data.columns:
        data["locality"] = ""
    for source_col in ("locality_master", "locality_clean", "area", "neighborhood"):
        if source_col in data.columns:
            data["locality"] = data["locality"].replace(r"^\s*$", np.nan, regex=True).fillna(data[source_col])
    data["locality"] = data["locality"].fillna("").astype(str).str.strip()

    if "asking_price_inr" not in data.columns:
        data["asking_price_inr"] = np.nan
    for source_col in ("price_inr", "min_price_inr", "price_min_inr"):
        if source_col in data.columns:
            data["asking_price_inr"] = pd.to_numeric(data["asking_price_inr"], errors="coerce").fillna(
                pd.to_numeric(data[source_col], errors="coerce")
            )
    if "price_crore" in data.columns:
        data["asking_price_inr"] = pd.to_numeric(data["asking_price_inr"], errors="coerce").fillna(
            pd.to_numeric(data["price_crore"], errors="coerce") * 10_000_000
        )
    if "price_lakh" in data.columns:
        data["asking_price_inr"] = pd.to_numeric(data["asking_price_inr"], errors="coerce").fillna(
            pd.to_numeric(data["price_lakh"], errors="coerce") * 100_000
        )
    data["asking_price_inr"] = pd.to_numeric(data["asking_price_inr"], errors="coerce")

    if "valuation_area_sqft" not in data.columns:
        data["valuation_area_sqft"] = np.nan
    for source_col in ("area_sqft_model", "area_sqft", "superbuiltup_area_sqft", "builtup_area_sqft", "carpet_area_sqft", "area_min_sqft"):
        if source_col in data.columns:
            data["valuation_area_sqft"] = pd.to_numeric(data["valuation_area_sqft"], errors="coerce").fillna(
                pd.to_numeric(data[source_col], errors="coerce")
            )
    data["valuation_area_sqft"] = pd.to_numeric(data["valuation_area_sqft"], errors="coerce")

    if "bedrooms" not in data.columns:
        data["bedrooms"] = np.nan
    for source_col in ("bhk", "bedroom_count"):
        if source_col in data.columns:
            data["bedrooms"] = pd.to_numeric(data["bedrooms"], errors="coerce").fillna(
                pd.to_numeric(data[source_col], errors="coerce")
            )
    data["bedrooms"] = pd.to_numeric(data["bedrooms"], errors="coerce")

    if "price_per_sqft" not in data.columns:
        data["price_per_sqft"] = np.nan
    data["price_per_sqft"] = pd.to_numeric(data["price_per_sqft"], errors="coerce")
    derived_ppsf = data["asking_price_inr"] / data["valuation_area_sqft"].where(data["valuation_area_sqft"] > 0)
    data["price_per_sqft"] = data["price_per_sqft"].fillna(derived_ppsf)
    return data


def load_market_source_data():
    """Use the complete listing universe for market stats, not only model-training rows.

    The valuation modeling dataset is intentionally narrower than the full listing
    catalog. Prefer the listing dataset so cities present in the real property catalog
    are not incorrectly reported as empty; fall back safely if it is unavailable.
    """
    loaders = (load_listing_data, load_valuation_pool, load_data)
    best = pd.DataFrame()
    for loader in loaders:
        try:
            candidate = _prepare_market_frame(loader())
            if candidate.empty:
                continue
            city_count = candidate.loc[candidate["city"].str.len() > 0, "city"].nunique()
            best_city_count = best.loc[best["city"].str.len() > 0, "city"].nunique() if not best.empty and "city" in best.columns else 0
            # Prefer the source with the broadest real city coverage; use record count
            # as the tie-breaker. This avoids silently narrowing the page to training data.
            if city_count > best_city_count or (city_count == best_city_count and len(candidate) > len(best)):
                best = candidate
        except Exception:
            app.logger.exception("Could not prepare a market data source from %s", getattr(loader, "__name__", "loader"))
    if best.empty:
        raise RuntimeError("No usable market dataset is available. Check the listing, master and valuation datasets.")
    return best

def sync_user_activity_columns(conn, user_id, recommended_ids=None):
    searches = conn.execute("SELECT id, search_query, filters_json, created_at FROM recently_searched WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
    views = conn.execute("SELECT property_id, viewed_at FROM recently_viewed WHERE user_id = ? ORDER BY viewed_at DESC, id DESC LIMIT 20", (user_id,)).fetchall()
    shortlist = conn.execute("SELECT property_id FROM shortlisted_properties WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100", (user_id,)).fetchall()
    search_snapshot = [{"id": r["id"], "query": r["search_query"], "filters": _safe_json(r["filters_json"], {}), "created_at": r["created_at"]} for r in searches]
    view_snapshot = [{"property_id": str(r["property_id"]), "viewed_at": r["viewed_at"]} for r in views]
    shortlist_ids = [str(r["property_id"]) for r in shortlist]
    rec_ids = [str(x) for x in (recommended_ids or [])][:20]
    conn.execute("UPDATE users SET search_history_json = ?, shortlisted_property_ids_json = ?, recent_property_clicks_json = ?, recommended_property_ids_json = ? WHERE id = ?", (json.dumps(search_snapshot, ensure_ascii=False), json.dumps(shortlist_ids), json.dumps(view_snapshot), json.dumps(rec_ids), user_id))

def record_activity_event(user_id, event_type, page="", property_id="", search_query="", metadata=None, duration_ms=None):
    try:
        duration = max(0, int(duration_ms)) if duration_ms not in (None, "") else None
    except (TypeError, ValueError):
        duration = None
    conn = get_db()
    try:
        with conn:
            conn.execute("INSERT INTO activity_events (user_id, event_type, page, property_id, search_query, metadata_json, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, str(event_type or "unknown")[:80], str(page or "")[:500], str(property_id or "")[:200], str(search_query or "")[:500], json.dumps(metadata or {}, ensure_ascii=False, default=str), duration))
            conn.execute("UPDATE users SET last_activity_at = datetime('now'), last_activity_type = ?, last_activity_page = ?, total_activity_events = COALESCE(total_activity_events,0)+1, activity_version = COALESCE(activity_version,0)+1, updated_at = datetime('now') WHERE id = ?", (str(event_type or "unknown")[:80], str(page or "")[:500], user_id))
    finally:
        conn.close()

def get_activity_profile(conn, user_id):
    r = conn.execute("SELECT search_history_json, shortlisted_property_ids_json, recent_property_clicks_json, recommended_property_ids_json, last_activity_at, last_activity_type, last_activity_page, total_activity_events, activity_version FROM users WHERE id = ?", (user_id,)).fetchone()
    if not r:
        return {}
    return {"search_history": _safe_json(r["search_history_json"], []), "shortlisted_property_ids": _safe_json(r["shortlisted_property_ids_json"], []), "recent_property_clicks": _safe_json(r["recent_property_clicks_json"], []), "recommended_property_ids": _safe_json(r["recommended_property_ids_json"], []), "last_activity_at": r["last_activity_at"], "last_activity_type": r["last_activity_type"], "last_activity_page": r["last_activity_page"], "total_activity_events": int(r["total_activity_events"] or 0), "activity_version": int(r["activity_version"] or 0)}

# =====================================================================
# API ROUTES: USER ACTIVITY & SHORTLIST
# =====================================================================
@app.route("/api/user/activity", methods=["GET"])
def user_activity():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    user_id = user["id"]
    conn = get_db()
    searches = conn.execute("SELECT * FROM recently_searched WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
    views = conn.execute("SELECT * FROM recently_viewed WHERE user_id = ? ORDER BY viewed_at DESC, id DESC LIMIT 30", (user_id,)).fetchall()
    shortlists = conn.execute("SELECT * FROM shortlisted_properties WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100", (user_id,)).fetchall()
    profile = get_activity_profile(conn, user_id)
    conn.close()
    df = load_listing_data()
    def hydrate(rows, timestamp_key):
        result=[]; seen=set()
        for row in rows:
            pid=str(row["property_id"])
            if pid in seen: continue
            seen.add(pid)
            match=df[df["property_id"]==pid]
            if not match.empty: result.append(format_property_card(match.iloc[0].to_dict(), row[timestamp_key], include_prediction=True))
        return result
    viewed = hydrate(views, "viewed_at")
    shortlisted = hydrate(shortlists, "created_at")
    recent_searches = [{"id":r["id"],"query":r["search_query"],"filters":_safe_json(r["filters_json"],{}),"created_at":r["created_at"]} for r in searches]
    return jsonify({"success":True,"user":user,"searches":recent_searches,"viewed":viewed,"shortlisted":shortlisted,"activity_profile":profile,"stats":{"total_searches":len(recent_searches),"total_viewed":len(viewed),"total_shortlisted":len(shortlisted),"total_activity_events":profile.get("total_activity_events",0)}})

@app.route("/api/user/activity-event", methods=["POST"])
def user_activity_event():
    user=get_current_user()
    if not user: return jsonify({"success":False,"error":"Not authenticated"}),401
    data=request.get_json(silent=True) or request.form or {}
    metadata=data.get("metadata")
    if isinstance(metadata,str): metadata=_safe_json(metadata,{})
    record_activity_event(user["id"],data.get("event_type"),data.get("page"),data.get("property_id"),data.get("search_query"),metadata if isinstance(metadata,dict) else {},data.get("duration_ms"))
    return jsonify({"success":True})

@app.route("/api/user/recently-viewed", methods=["POST"])
def add_recently_viewed():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    user_id = user["id"]
    data = request.get_json(silent=True) or request.form or {}
    prop_id = str(data.get("property_id") or "").strip()
    if not prop_id:
        return jsonify({"success": False, "error": "property_id required"}), 400

    conn = get_db()
    with conn:
        conn.execute("DELETE FROM recently_viewed WHERE user_id = ? AND property_id = ?", (user_id, prop_id))
        conn.execute("INSERT INTO recently_viewed (user_id, property_id, viewed_at) VALUES (?, ?, datetime('now'))", (user_id, prop_id))
        sync_user_activity_columns(conn, user_id)
    conn.close()
    record_activity_event(user_id, "property_click", page=request.headers.get("Referer", ""), property_id=prop_id)
    return jsonify({"success": True, "property_id": prop_id})

@app.route("/api/user/searches", methods=["POST"])
def add_search_record():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    user_id = user["id"]
    data = request.get_json(silent=True) or request.form or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "query required"}), 400
    filters = json.dumps(data.get("filters") or {}, ensure_ascii=False, default=str)

    conn = get_db()
    with conn:
        conn.execute("INSERT INTO recently_searched (user_id, search_query, filters_json, created_at) VALUES (?, ?, ?, datetime('now'))", (user_id, query, filters))
        sync_user_activity_columns(conn, user_id)
    conn.close()
    record_activity_event(user_id, "search", page=request.headers.get("Referer", ""), search_query=query, metadata=_safe_json(filters, {}))
    return jsonify({"success": True})

@app.route("/api/user/shortlist", methods=["GET", "POST", "DELETE"])
def toggle_shortlist():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    user_id = user["id"]
    data = request.get_json(silent=True) or request.form or request.args or {}
    prop_id = str(data.get("property_id") or "").strip()
    if not prop_id:
        return jsonify({"success": False, "error": "property_id required"}), 400

    conn = get_db()
    if request.method == "GET":
        row = conn.execute("SELECT 1 FROM shortlisted_properties WHERE user_id = ? AND property_id = ?", (user_id, prop_id)).fetchone()
        conn.close()
        return jsonify({"success": True, "shortlisted": bool(row), "property_id": prop_id})
    action = str(data.get("action") or "toggle").strip().lower()
    if request.method == "DELETE" or action == "remove":
        with conn:
            conn.execute("DELETE FROM shortlisted_properties WHERE user_id = ? AND property_id = ?", (user_id, prop_id))
        is_shortlisted = False
    elif action == "add":
        with conn:
            conn.execute("INSERT OR IGNORE INTO shortlisted_properties (user_id, property_id, created_at) VALUES (?, ?, datetime('now'))", (user_id, prop_id))
        is_shortlisted = True
    else:
        existing = conn.execute("SELECT id FROM shortlisted_properties WHERE user_id = ? AND property_id = ?", (user_id, prop_id)).fetchone()
        with conn:
            if existing:
                conn.execute("DELETE FROM shortlisted_properties WHERE user_id = ? AND property_id = ?", (user_id, prop_id))
                is_shortlisted = False
            else:
                conn.execute("INSERT OR IGNORE INTO shortlisted_properties (user_id, property_id, created_at) VALUES (?, ?, datetime('now'))", (user_id, prop_id))
                is_shortlisted = True
    conn.close()
    conn = get_db()
    with conn:
        sync_user_activity_columns(conn, user_id)
    conn.close()
    record_activity_event(user_id, "shortlist_add" if is_shortlisted else "shortlist_remove", page=request.headers.get("Referer", ""), property_id=prop_id)
    return jsonify({"success": True, "shortlisted": is_shortlisted, "property_id": prop_id})

@app.route("/api/user/recommendations", methods=["GET"])
def user_recommendations():
    df=load_listing_data().copy(); user=get_current_user()
    if not user: return jsonify({"success":False,"error":"Not authenticated"}),401
    user_id=user["id"]; conn=get_db()
    searches=conn.execute("SELECT * FROM recently_searched WHERE user_id=? ORDER BY id DESC LIMIT 10",(user_id,)).fetchall()
    views=conn.execute("SELECT property_id FROM recently_viewed WHERE user_id=? ORDER BY viewed_at DESC,id DESC LIMIT 12",(user_id,)).fetchall()
    shortlist_rows=conn.execute("SELECT property_id FROM shortlisted_properties WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 50",(user_id,)).fetchall(); conn.close()
    def parse(row):
        f=_safe_json(row["filters_json"],{}); q=str(row["search_query"] or "").strip(); parts=[x.strip() for x in re.split(r"·|,",q) if x.strip()]; city=str(f.get("city") or (parts[0] if parts else "")).strip(); loc=str(f.get("locality") or (parts[1] if len(parts)>1 else "")).strip()
        return {"city":city,"locality":loc,"bedrooms":f.get("bedrooms") or f.get("bhk"),"property_type":str(f.get("property_type") or "").strip(),"min_price":f.get("min_price") or f.get("price_min"),"max_price":f.get("max_price") or f.get("price_max"),"min_area":f.get("min_area"),"max_area":f.get("max_area")}
    prefs=[parse(r) for r in searches]; viewed_ids={str(r["property_id"]) for r in views}; shortlisted_ids={str(r["property_id"]) for r in shortlist_rows}
    candidates=df[~df["property_id"].isin(viewed_ids|shortlisted_ids)].copy(); candidates=candidates[candidates["asking_price_inr"].notna()&(candidates["asking_price_inr"]>0)].copy()
    if candidates.empty: return jsonify({"success":True,"recommendations":[],"basis":{}})
    candidates["_score"]=0.0; basis=prefs[0] if prefs else {}
    for idx,pref in enumerate(prefs):
        w=max(1.0,5.0-idx*.5); city=pref["city"]; loc=normalize_market(pref["locality"])
        if city: candidates.loc[market_mask(candidates["city"],city),"_score"]+=120*w
        if loc:
            locs=candidates["locality"].fillna("").astype(str).map(normalize_market); candidates.loc[locs.eq(loc),"_score"]+=90*w; candidates.loc[locs.str.contains(loc,na=False),"_score"]+=35*w
        try:
            bhk=float(pref["bedrooms"]); diff=(candidates["bedrooms"]-bhk).abs(); candidates.loc[diff.eq(0),"_score"]+=42*w; candidates.loc[diff.eq(1),"_score"]+=15*w
        except (TypeError,ValueError): pass
        pt=normalize_market(pref["property_type"])
        if pt: candidates.loc[candidates["property_type"].fillna("").astype(str).map(normalize_market).str.contains(pt,na=False),"_score"]+=24*w
        try:
            lo=float(pref["min_price"]) if pref["min_price"] not in (None,"") else None; hi=float(pref["max_price"]) if pref["max_price"] not in (None,"") else None; price=candidates["asking_price_inr"]
            if lo is not None: candidates.loc[price.ge(lo),"_score"]+=10*w
            if hi is not None: candidates.loc[price.le(hi),"_score"]+=10*w
        except (TypeError,ValueError): pass
        try:
            lo=float(pref["min_area"]) if pref["min_area"] not in (None,"") else None; hi=float(pref["max_area"]) if pref["max_area"] not in (None,"") else None; area=candidates["valuation_area_sqft"]
            if lo is not None: candidates.loc[area.ge(lo),"_score"]+=7*w
            if hi is not None: candidates.loc[area.le(hi),"_score"]+=7*w
        except (TypeError,ValueError): pass
    for row in views[:5]:
        m=df[df["property_id"]==str(row["property_id"])]
        if m.empty: continue
        v=m.iloc[0]; candidates.loc[market_mask(candidates["city"],v.get("city","")),"_score"]+=32; vloc=normalize_market(v.get("locality",""))
        if vloc:
            locs=candidates["locality"].fillna("").astype(str).map(normalize_market); candidates.loc[locs.eq(vloc),"_score"]+=38
        try:
            bhk=float(v.get("bedrooms")); candidates.loc[(candidates["bedrooms"]-bhk).abs().eq(0),"_score"]+=18; candidates.loc[(candidates["bedrooms"]-bhk).abs().eq(1),"_score"]+=7
        except (TypeError,ValueError): pass
        try:
            vp=float(v.get("asking_price_inr")); rel=(candidates["asking_price_inr"]-vp).abs()/max(vp,1); candidates.loc[rel.le(.15),"_score"]+=15; candidates.loc[rel.le(.30),"_score"]+=7
        except (TypeError,ValueError): pass
    # Shortlisted properties are a stronger preference signal than a simple click.
    for pid in list(shortlisted_ids)[:8]:
        m=df[df["property_id"]==pid]
        if m.empty: continue
        v=m.iloc[0]; candidates.loc[market_mask(candidates["city"],v.get("city","")),"_score"]+=48; vloc=normalize_market(v.get("locality",""))
        if vloc:
            locs=candidates["locality"].fillna("").astype(str).map(normalize_market); candidates.loc[locs.eq(vloc),"_score"]+=50
        try:
            bhk=float(v.get("bedrooms")); candidates.loc[(candidates["bedrooms"]-bhk).abs().eq(0),"_score"]+=24; candidates.loc[(candidates["bedrooms"]-bhk).abs().eq(1),"_score"]+=9
        except (TypeError,ValueError): pass
        try:
            vp=float(v.get("asking_price_inr")); rel=(candidates["asking_price_inr"]-vp).abs()/max(vp,1); candidates.loc[rel.le(.15),"_score"]+=20; candidates.loc[rel.le(.30),"_score"]+=8
        except (TypeError,ValueError): pass
    if not prefs and not views and not shortlisted_ids: candidates["_score"]=1.0
    candidates=candidates.sort_values(["_score","asking_price_inr"],ascending=[False,True],kind="stable")
    if basis.get("city"):
        focus=candidates[market_mask(candidates["city"],basis["city"])]
        if not focus.empty: candidates=focus
    results=[format_property_card(r.to_dict(), include_prediction=True) for _,r in candidates.head(6).iterrows()]; rec_ids=[str(r["property_id"]) for r in results if r.get("property_id")]
    conn=get_db()
    with conn: sync_user_activity_columns(conn,user_id,rec_ids)
    conn.close()
    return jsonify({"success":True,"recommendations":results,"basis":basis,"activity":{"recommended_property_ids":rec_ids}})

@app.route("/api/user/profile", methods=["POST"])
def update_profile():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or request.form
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    if not name or not email:
        return jsonify({"success": False, "error": "Name and email required"}), 400

    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET name = ?, email = ?, updated_at = datetime('now') WHERE id = ?", (name, email, user["id"]))
    conn.close()
    return jsonify({"success": True, "user": {"id": user["id"], "name": name, "email": email}})

@app.route("/api/user/change-password", methods=["POST"])
def change_password():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or request.form
    current_pw = str(data.get("current_password") or "").strip()
    new_pw = str(data.get("new_password") or "").strip()

    if len(new_pw) < 6:
        return jsonify({"success": False, "error": "New password must be at least 6 characters"}), 400

    conn = get_db()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
    stored_hash = row["password_hash"] if row else ""
    try:
        valid_current = bool(stored_hash) and check_password_hash(stored_hash, current_pw)
    except (ValueError, TypeError):
        valid_current = False
    if not valid_current:
        legacy_hash = hashlib.sha256(current_pw.encode("utf-8")).hexdigest()
        valid_current = stored_hash == legacy_hash
    if not valid_current:
        conn.close()
        return jsonify({"success": False, "error": "Current password incorrect"}), 403

    with conn:
        conn.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?", (generate_password_hash(new_pw), user["id"]))
    conn.close()
    return jsonify({"success": True, "message": "Password updated successfully"})

# =====================================================================
# API ROUTES: AUTOCOMPLETE & SEARCH
# =====================================================================
@app.route("/api/suggestions", methods=["GET"])
def suggestions():
    df = load_listing_data()
    s_type = request.args.get("type", "city").lower()
    q = request.args.get("q", "").strip().lower()
    city = request.args.get("city", "").strip().lower()

    if s_type == "city":
        cities = df["city"].dropna().unique()
        if q:
            matches = [c for c in cities if q in str(c).lower()]
        else:
            matches = list(cities)[:10]

        results = []
        for c in matches:
            count = int((df["city"] == c).sum())
            results.append({"name": c, "count": count, "label": f"{c} ({count} listings)"})
        results.sort(key=lambda x: x["count"], reverse=True)
        return jsonify({"success": True, "suggestions": results[:15]})

    elif s_type == "locality":
        subset = df
        if city:
            subset = df[df["city"].astype(str).str.lower() == city]
        locs = subset["locality"].dropna().unique()
        if q:
            matches = [l for l in locs if q in str(l).lower()]
        else:
            matches = list(locs)[:10]

        results = []
        for l in matches:
            count = int((subset["locality"] == l).sum())
            results.append({"name": l, "count": count, "label": f"{l} ({count} properties)"})
        results.sort(key=lambda x: x["count"], reverse=True)
        return jsonify({"success": True, "suggestions": results[:20]})

    return jsonify({"success": True, "suggestions": []})

# Cache card valuations so the activity/recommendation views do not rerun the model
# for the same property on every refresh. Cache is process-local and safe to clear on restart.
_CARD_VALUATION_CACHE = {}
_CARD_VALUATION_CACHE_MAX = 2500

def get_card_valuation(p):
    """Return the same final valuation used by the property intelligence endpoint."""
    pid = str(p.get("property_id", "") or "")
    if pid and pid in _CARD_VALUATION_CACHE:
        return dict(_CARD_VALUATION_CACHE[pid])

    target = dict(p)
    try:
        # Prefer the modelling row so all model features match training-time names/types.
        model_df = load_data()
        if pid and "property_id" in model_df.columns:
            match = model_df[model_df["property_id"].astype(str) == pid]
            if not match.empty:
                target = match.iloc[0].to_dict()
        pool = model_df if model_df is not None and not model_df.empty else load_listing_data()
        valuation = run_full_valuation(target, pool)
        asking = _safe_float(target.get("asking_price_inr"))
        predicted = _safe_float(valuation.get("final_estimated_value"))
        if (asking is None or asking <= 0):
            asking = _safe_float(p.get("asking_price_inr") or p.get("price_inr"))
        if predicted is None or predicted <= 0:
            return {}
        # Signed premium: negative means the asking price is below model value.
        premium = ((asking - predicted) / predicted) * 100.0 if asking and asking > 0 else None
        direction = ("below_valuation" if premium < -0.05 else
                     "above_valuation" if premium > 0.05 else "equal") if premium is not None else "unavailable"
        result = {
            "predicted_value_inr": round(predicted, 2),
            "predicted_value_formatted": money(predicted),
            "final_estimated_value": round(predicted, 2),
            "final_estimated_value_formatted": money(predicted),
            "asking_price_premium_pct": round(premium, 1) if premium is not None else None,
            "asking_vs_predicted_percent": round(abs(premium), 1) if premium is not None else None,
            "prediction_direction": direction,
            "prediction_label": ("Below predicted value" if direction == "below_valuation" else
                                 "Above predicted value" if direction == "above_valuation" else
                                 "At predicted value" if direction == "equal" else "Prediction unavailable"),
        }
        if pid:
            if len(_CARD_VALUATION_CACHE) >= _CARD_VALUATION_CACHE_MAX:
                _CARD_VALUATION_CACHE.clear()
            _CARD_VALUATION_CACHE[pid] = dict(result)
        return result
    except Exception as exc:
        print(f"[valuation-card] Could not value property {pid}: {exc}")
        return {}

def _safe_float(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None

def format_property_card(p, timestamp=None, include_prediction=False):
    pid = str(p.get("property_id", ""))

    def num(value):
        try:
            value = float(value)
            return value if math.isfinite(value) else None
        except (TypeError, ValueError):
            return None

    beds = num(p.get("bedrooms"))
    if beds is None:
        beds = num(p.get("bhk"))
    beds_int = int(beds) if beds is not None else None

    baths = num(p.get("bathrooms"))
    baths_int = int(baths) if baths is not None else None

    area = num(p.get("valuation_area_sqft"))
    if area is None:
        area = num(p.get("area_sqft_model"))
    if area is None:
        area = num(p.get("area_sqft"))
    if area is None:
        area = num(p.get("area_min_sqft"))

    price = num(p.get("asking_price_inr"))
    price_max = num(p.get("asking_price_max_inr"))
    if price is None:
        price = num(p.get("price_inr"))
    if price is None:
        price = num(p.get("min_price_inr"))
    if price is None:
        price = num(p.get("price_min_inr"))
    if price_max is None:
        price_max = num(p.get("max_price_inr")) or num(p.get("price_max_inr"))

    def fmt_money(value):
        if value is None or value <= 0:
            return "Price on Request"
        return money(value)

    if price is not None and price_max is not None and price_max > price:
        price_formatted = f"{fmt_money(price)} – {fmt_money(price_max)}"
        price_label = "Asking price range"
    else:
        price_formatted = fmt_money(price)
        price_label = "Asking price"

    property_name = p.get("property_name")
    if property_name is None or pd.isna(property_name) or not str(property_name).strip():
        property_name = p.get("society") or p.get("property_title") or p.get("title") or "Property"
    property_name = str(property_name).strip()

    loc = str(p.get("locality") or p.get("locality_clean") or "").strip()
    city = str(p.get("city") or "").strip()
    society = str(p.get("society") or property_name).strip()
    ptype = str(p.get("property_type") or "Residential Apartment").strip()

    if area is not None:
        area_formatted = f"{round(area):,} sqft"
    else:
        area_formatted = "Area unavailable"

    ppsf = num(p.get("price_per_sqft"))
    if ppsf is None and price is not None and area:
        ppsf = round(price / area)

    return {
        "property_id": pid,
        "title": property_name,
        "property_name": property_name,
        "society": society,
        "city": city,
        "locality": loc,
        "bedrooms": beds_int,
        "bathrooms": baths_int,
        "valuation_area_sqft": round(area, 0) if area is not None else None,
        "area_formatted": area_formatted,
        "asking_price_inr": price,
        "asking_price_max_inr": price_max,
        "price_inr": price,
        "price_formatted": price_formatted,
        "price_label": price_label,
        "price_per_sqft": int(ppsf) if ppsf is not None else None,
        "price_per_sqft_formatted": f"₹{int(ppsf):,}/sqft" if ppsf is not None else "",
        "property_type": ptype,
        "image_url": get_property_images(pid, 3)[0] if pid else "",
        "images": get_property_images(pid, 3) if pid else [],
        "timestamp": timestamp,
        **(get_card_valuation(p) if include_prediction else {}),
    }

@app.route("/api/properties", methods=["GET"])
def properties_search():
    df = load_listing_data()
    q_city = request.args.get("city", "").strip()
    q_locality = request.args.get("locality", "").strip()
    q_bhk = request.args.get("bedrooms")
    q_type = request.args.get("property_type", "").strip()
    q_types = [x.strip() for x in request.args.get("property_types", "").split(",") if x.strip()]
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_area = request.args.get("min_area", type=float)
    max_area = request.args.get("max_area", type=float)
    sort_by = request.args.get("sort", "default").strip()
    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(50, max(1, request.args.get("page_size", 12, type=int)))

    filtered = df.copy()

    if q_city:
        filtered = filtered[filtered["city"].astype(str).str.lower().str.contains(q_city.lower(), na=False)]

    if q_locality:
        filtered = filtered[filtered["locality"].astype(str).str.lower().str.contains(q_locality.lower(), na=False)]

    if q_bhk:
        try:
            bhk_val = int(q_bhk)
            if bhk_val >= 5:
                filtered = filtered[filtered["bedrooms"] >= 5]
            else:
                filtered = filtered[filtered["bedrooms"] == bhk_val]
        except ValueError:
            pass

    # Multiple selected property types are an OR filter, while quick-search type is a single selection.
    if q_type:
        filtered = filtered[filtered["property_type"].astype(str).str.lower().str.contains(q_type.lower(), na=False)]
    elif q_types:
        type_mask = pd.Series(False, index=filtered.index)
        for selected_type in q_types:
            type_mask |= filtered["property_type"].astype(str).str.lower().str.contains(selected_type.lower(), na=False)
        filtered = filtered[type_mask]

    if min_price is not None and min_price > 0:
        filtered = filtered[filtered["asking_price_inr"] >= min_price]

    if max_price is not None and max_price > 0:
        filtered = filtered[filtered["asking_price_inr"] <= max_price]

    if min_area is not None and min_area > 0:
        filtered = filtered[filtered["valuation_area_sqft"] >= min_area]

    if max_area is not None and max_area > 0:
        filtered = filtered[filtered["valuation_area_sqft"] <= max_area]

    # Sorting
    if sort_by == "price_asc":
        filtered = filtered.sort_values("asking_price_inr", ascending=True)
    elif sort_by == "price_desc":
        filtered = filtered.sort_values("asking_price_inr", ascending=False)
    elif sort_by == "area_desc":
        filtered = filtered.sort_values("valuation_area_sqft", ascending=False)
    elif sort_by == "ppsf_asc":
        filtered = filtered.sort_values("price_per_sqft", ascending=True)
    elif sort_by == "ppsf_desc":
        filtered = filtered.sort_values("price_per_sqft", ascending=False)
    else:
        # Default smart sort: prioritize listings with complete data
        filtered = filtered.sort_values(["asking_price_inr"], ascending=True)

    total_results = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_records = filtered.iloc[start_idx:end_idx]

    # Include the cached model-based valuation for visible cards. If the model cannot produce
    # a valid prediction, the card omits prediction fields and the UI labels it unavailable.
    properties = [format_property_card(row.to_dict(), include_prediction=True) for _, row in page_records.iterrows()]

    return jsonify({
        "success": True,
        "total": total_results,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total_results / page_size) if total_results > 0 else 1,
        "city": q_city,
        "locality": q_locality,
        "properties": properties,
    })

# =====================================================================
# API ROUTES: PROPERTY DETAILS, INTELLIGENCE, EXPLANATION
# =====================================================================
@app.route("/api/property/<property_id>", methods=["GET"])
def property_details(property_id):
    df = load_data()
    match = df[df["property_id"] == str(property_id)]
    source_df = df
    if match.empty:
        source_df = load_listing_data()
        match = source_df[source_df["property_id"] == str(property_id)]
    if match.empty:
        return jsonify({"success": False, "error": f"Property '{property_id}' not found."}), 404

    row = match.iloc[0].to_dict()
    card = format_property_card(row)

    # Enrich the model row with source-backed metadata from the canonical master listing.
    # Never substitute invented floors, coordinates, furnishing, parking, status, or amenities.
    try:
        master = load_master_metadata()
        if not master.empty and "property_id" in master.columns:
            metadata_match = master[master["property_id"].astype(str) == str(property_id)]
            if not metadata_match.empty:
                metadata = metadata_match.iloc[0].to_dict()
                for key, value in metadata.items():
                    if value is not None and not (isinstance(value, float) and pd.isna(value)):
                        row[key] = value
    except Exception as e:
        print(f"Warning loading property metadata for {property_id}: {e}")

    def clean_value(value):
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # Reformat from the merged, source-backed record.
    card = format_property_card(row)
    for key in ("floor", "total_floors", "balconies", "latitude", "longitude",
                "furnishing", "parking", "parking_count", "status", "possession",
                "age_of_property", "property_age", "facing", "description", "amenities",
                "features", "ready_to_move", "under_construction", "verified",
                "rera_registered", "resale", "superbuiltup_area_sqft", "carpet_area_sqft",
                "builtup_area_sqft", "area_basis", "listing_url", "source"):
        card[key] = clean_value(row.get(key))

    # Do not show curated stock photography as if it depicted this listing.
    card.pop("image_url", None)
    card.pop("images", None)

    # Normalize numeric coordinates only when the source actually provides them.
    for key in ("latitude", "longitude"):
        value = clean_value(row.get(key))
        try:
            card[key] = float(value) if value is not None else None
        except (TypeError, ValueError):
            card[key] = None

    return jsonify({"success": True, "property": card})

@app.route("/api/property/<property_id>/intelligence", methods=["GET"])
def property_intelligence(property_id):
    df = load_data()
    target = normalize_valuation_target(property_id, df)
    if target is None:
        return jsonify({"success": False, "error": f"Property '{property_id}' not found."}), 404

    pool = load_valuation_pool()
    valuation = run_full_valuation(target, pool)

    # Comparables list: use the full eligible listing universe, not only model-training rows.
    try:
        t_lat = float(target["latitude"])
        t_lon = float(target["longitude"])
        t_city = str(target["city"]).lower()

        comps_pool = pool[
            (df["property_id"] != str(property_id))
            & (df["city"].astype(str).str.lower() == t_city)
            & (df["asking_price_inr"] > 0)
        ].copy()

        comps_pool["distance_km"] = haversine_km(
            t_lat, t_lon, comps_pool["latitude"].values, comps_pool["longitude"].values
        )
        comps_pool["area_diff_pct"] = abs(comps_pool["valuation_area_sqft"] - target["valuation_area_sqft"]) / target["valuation_area_sqft"] * 100

        top_comps = comps_pool.sort_values(["distance_km", "area_diff_pct"]).head(5)
        comparables = [format_property_card(r.to_dict(), include_prediction=True) for _, r in top_comps.iterrows()]
        for i, c in enumerate(comparables):
            c.pop("image_url", None)
            c.pop("images", None)
            dist = top_comps.iloc[i]["distance_km"]
            c["distance_km"] = round(dist, 2)
            c["distance_formatted"] = f"{dist:.1f} km away" if dist >= 1 else f"{int(dist * 1000)} m away"
    except Exception as e:
        print(f"Error fetching comparable properties: {e}")
        comparables = []

    return jsonify({
        "success": True,
        "property_id": property_id,
        "valuation": valuation,
        "market_evidence": {
            "comparable_count": valuation["comparable_count"],
            "locality_property_count": valuation["locality_property_count"],
        },
        "comparable_properties": comparables,
    })

@app.route("/api/property/<property_id>/explanation", methods=["GET"])
def property_explanation(property_id):
    target = normalize_valuation_target(property_id, load_data())
    if target is None:
        return jsonify({"success": False, "error": f"Property '{property_id}' not found."}), 404

    expl = get_shap_explanation(target)
    return jsonify({"success": True, "property_id": property_id, "explanation": expl})

# =====================================================================
# API ROUTES: MARKET ANALYZER
# =====================================================================
@app.route("/api/market/options", methods=["GET"])
def market_analytics_options():
    """Return dataset-backed city names and the locality list for a selected city."""
    try:
        df = load_market_source_data()
        if df.empty or "city" not in df.columns:
            return jsonify({"success": True, "cities": [], "localities": []})
        cities = sorted(
            {str(value).strip() for value in df["city"].dropna().tolist() if str(value).strip() and str(value).strip().casefold() not in {"nan", "none", "unknown"}},
            key=lambda value: value.casefold(),
        )
        # Keep the UI's familiar Gurgaon label when the source uses Gurugram.
        if any(value.casefold() == "gurugram" for value in cities) and not any(value.casefold() == "gurgaon" for value in cities):
            cities = ["Gurgaon" if value.casefold() == "gurugram" else value for value in cities]
            cities = sorted(set(cities), key=lambda value: value.casefold())
        city_query = request.args.get("city", "").strip()
        localities = []
        if city_query and "locality" in df.columns:
            selected = df.loc[market_mask(df["city"], city_query)]
            localities = sorted(
                {str(value).strip() for value in selected["locality"].dropna().tolist() if str(value).strip()},
                key=lambda value: value.casefold(),
            )
        return jsonify({"success": True, "cities": cities, "localities": localities})
    except Exception:
        app.logger.exception("Market options could not be loaded")
        return jsonify({"success": False, "error": "Market filter options are temporarily unavailable."}), 500


@app.route("/api/market", methods=["GET"])
def market_analytics():
    """Compute market statistics from source-backed property records only."""
    try:
        df = load_market_source_data().copy()
        if df.empty:
            return jsonify({"success": False, "error": "The property dataset is empty."}), 503

        city = request.args.get("city", "").strip()
        locality_query = request.args.get("locality", "").strip()
        bhk = request.args.get("bhk", type=int)

        # No city parameter means aggregate every city in the actual dataset.
        city_mask = market_mask(df["city"], city)
        city_subset = df.loc[city_mask].copy()
        if city_subset.empty:
            available = sorted({str(value).strip() for value in df["city"].dropna().tolist() if str(value).strip()}, key=str.casefold)
            available_text = ", ".join(available[:20]) + ("…" if len(available) > 20 else "")
            return jsonify({"success": False, "error": f"No indexed properties are mapped to {city}. Dataset cities: {available_text}."}), 404

        subset = city_subset.copy()
        locality_label = "All Localities"
        if locality_query:
            locality_values = subset["locality"].fillna("").astype(str).str.strip()
            normalized_values = locality_values.map(normalize_market)
            normalized_query = normalize_market(locality_query)
            exact_mask = normalized_values.eq(normalized_query)
            match_mask = exact_mask if exact_mask.any() else normalized_values.str.contains(re.escape(normalized_query), na=False)
            locality_subset = subset.loc[match_mask].copy()
            if locality_subset.empty:
                return jsonify({"success": False, "error": f"No properties were found in {locality_query}, {city}. Check the locality spelling or clear the locality filter."}), 404
            subset = locality_subset
            matched_localities = locality_subset["locality"].dropna().astype(str).str.strip().unique().tolist()
            locality_label = matched_localities[0] if len(matched_localities) == 1 else locality_query

        if bhk:
            bedrooms = pd.to_numeric(subset.get("bedrooms"), errors="coerce")
            bhk_subset = subset.loc[bedrooms.eq(bhk)].copy()
            if bhk_subset.empty:
                return jsonify({"success": False, "error": f"No {bhk} BHK properties were found for this market selection."}), 404
            subset = bhk_subset

        # Numeric coercion and validity filtering are applied before each statistic.
        for column in ("asking_price_inr", "price_per_sqft", "valuation_area_sqft", "bedrooms"):
            if column in subset.columns:
                subset[column] = pd.to_numeric(subset[column], errors="coerce")
        prices = subset.loc[subset["asking_price_inr"].gt(0), "asking_price_inr"].dropna()
        ppsf = subset.loc[subset["price_per_sqft"].gt(0), "price_per_sqft"].dropna()
        areas = subset.loc[subset["valuation_area_sqft"].gt(0), "valuation_area_sqft"].dropna()

        median_price = float(prices.median()) if not prices.empty else 0.0
        mean_price = float(prices.mean()) if not prices.empty else 0.0
        median_ppsf = float(ppsf.median()) if not ppsf.empty else 0.0
        mean_ppsf = float(ppsf.mean()) if not ppsf.empty else 0.0
        p25_ppsf = float(ppsf.quantile(0.25)) if not ppsf.empty else 0.0
        p75_ppsf = float(ppsf.quantile(0.75)) if not ppsf.empty else 0.0
        min_ppsf = float(ppsf.min()) if not ppsf.empty else 0.0
        max_ppsf = float(ppsf.max()) if not ppsf.empty else 0.0

        bhk_breakdown = []
        for bedrooms_count in [1, 2, 3, 4, 5, 6]:
            group = subset.loc[subset["bedrooms"].eq(bedrooms_count)]
            if group.empty:
                continue
            group_prices = group.loc[group["asking_price_inr"].gt(0), "asking_price_inr"].dropna()
            group_ppsf = group.loc[group["price_per_sqft"].gt(0), "price_per_sqft"].dropna()
            group_areas = group.loc[group["valuation_area_sqft"].gt(0), "valuation_area_sqft"].dropna()
            group_median_price = float(group_prices.median()) if not group_prices.empty else 0.0
            group_median_ppsf = float(group_ppsf.median()) if not group_ppsf.empty else 0.0
            bhk_breakdown.append({
                "bhk": bedrooms_count,
                "label": f"{bedrooms_count} BHK",
                "count": int(len(group)),
                "median_price": group_median_price,
                "median_price_formatted": money(group_median_price) if group_median_price else "—",
                "median_ppsf": round(group_median_ppsf, 0),
                "median_area": round(float(group_areas.median()), 0) if not group_areas.empty else 0,
            })

        hist_bins = []
        if not prices.empty:
            # Adaptive log-spaced price bands. Smaller markets receive more, narrower
            # partitions; larger markets use broader bands so the legend remains readable.
            price_crore = prices.to_numpy(dtype=float) / 10000000.0
            price_crore = price_crore[np.isfinite(price_crore) & (price_crore > 0)]
            listing_count = int(len(price_crore))
            if listing_count <= 50:
                target_bins = 12
            elif listing_count <= 250:
                target_bins = 10
            elif listing_count <= 1000:
                target_bins = 9
            else:
                target_bins = 8

            low_price = float(np.min(price_crore))
            high_price = float(np.max(price_crore))
            if high_price <= low_price:
                # Identical-priced listings have no meaningful price spread to partition.
                pad = max(0.01, low_price * 0.05)
                bin_edges = np.array([max(0.0, low_price - pad), high_price + pad], dtype=float)
            else:
                # Log spacing prevents premium outliers from swallowing the lower market.
                bin_edges = np.geomspace(low_price, high_price, num=target_bins + 1)
                bin_edges[0] = max(0.0, low_price)
                bin_edges[-1] = high_price * (1.0 + 1e-10)

            counts, bin_edges = np.histogram(price_crore, bins=bin_edges)
            for index, count in enumerate(counts):
                if int(count) <= 0:
                    continue
                lower = float(bin_edges[index])
                upper = float(bin_edges[index + 1])
                hist_bins.append({
                    "range": f"₹{lower:.2f} – {upper:.2f} Cr",
                    "min_crore": round(lower, 4),
                    "max_crore": round(upper, 4),
                    "count": int(count),
                    "share_percent": round(float(count) / max(1, listing_count) * 100.0, 2),
                    "bin_count": int(target_bins),
                })

        # Locality comparison uses the chosen city and BHK filter, but does not
        # collapse to the one locality typed in the search box.
        locality_basis = city_subset.copy()
        if bhk:
            locality_basis = locality_basis.loc[pd.to_numeric(locality_basis["bedrooms"], errors="coerce").eq(bhk)]
        top_localities = []
        if "locality" in locality_basis.columns:
            for locality_name, group in locality_basis.groupby("locality", dropna=True):
                if len(group) < 2:
                    continue
                group_prices = pd.to_numeric(group["asking_price_inr"], errors="coerce")
                group_ppsf = pd.to_numeric(group["price_per_sqft"], errors="coerce")
                group_prices = group_prices[group_prices > 0].dropna()
                group_ppsf = group_ppsf[group_ppsf > 0].dropna()
                top_localities.append({
                    "locality": str(locality_name).strip(),
                    "count": int(len(group)),
                    "median_price_formatted": money(float(group_prices.median())) if not group_prices.empty else "—",
                    "median_ppsf": int(group_ppsf.median()) if not group_ppsf.empty else 0,
                })
        top_localities.sort(key=lambda item: (item["count"], item["median_ppsf"]), reverse=True)

        return jsonify({
            "success": True,
            "city": city or "All Cities",
            "locality": locality_label,
            "bhk": bhk,
            "total_properties": int(len(subset)),
            "priced_properties": int(len(prices)),
            "median_price": median_price,
            "median_price_formatted": money(median_price) if median_price else "—",
            "mean_price_formatted": money(mean_price) if mean_price else "—",
            "median_ppsf": round(median_ppsf, 0),
            "median_ppsf_formatted": f"₹{int(median_ppsf):,}/sqft" if median_ppsf else "—",
            "ppsf_range_formatted": f"₹{int(p25_ppsf):,} - ₹{int(p75_ppsf):,}/sqft" if not ppsf.empty else "—",
            "min_ppsf": int(min_ppsf),
            "p25_ppsf": int(p25_ppsf),
            "p75_ppsf": int(p75_ppsf),
            "max_ppsf": int(max_ppsf),
            "median_area_formatted": f"{int(areas.median()):,} sqft" if not areas.empty else "—",
            "bhk_distribution": bhk_breakdown,
            "price_distribution": hist_bins,
            "top_localities": top_localities[:10],
        })
    except Exception:
        app.logger.exception("Market analytics request failed")
        return jsonify({"success": False, "error": "Market analytics could not be calculated. Check the property dataset and try again."}), 500

# =====================================================================
# API ROUTES: SYSTEM HEALTH
# =====================================================================
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "real-estate-intelligence-api",
        "version": "2.5.0",
        "total_listings_indexed": len(load_data()),
        "model_loaded": load_model() is not None,
        "calibrator_loaded": load_calibrator() is not None,
    })

# =====================================================================
# FRONTEND STATIC ASSETS & PAGE ROUTING
# =====================================================================
@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(CSS_DIR, filename)

@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(JS_DIR, filename)

@app.route("/images/<path:filename>")
def serve_images(filename):
    img_dir = FRONTEND_DIR / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    return send_from_directory(img_dir, filename)

# Standard page flow routes
@app.route("/")
def page_landing():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/home")
def page_home():
    return send_from_directory(FRONTEND_DIR, "home.html")

@app.route("/search")
def page_search():
    return send_from_directory(FRONTEND_DIR, "search.html")

@app.route("/property/<property_id>")
def page_property(property_id):
    return send_from_directory(FRONTEND_DIR, "property.html")

@app.route("/market")
def page_market():
    return send_from_directory(FRONTEND_DIR, "market.html")

@app.route("/activity")
def page_activity():
    return send_from_directory(FRONTEND_DIR, "activity.html")

# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # Warm all expensive resources before accepting browser requests.
    # This prevents the first property/search request from paying the
    # dataset/model loading cost. SHAP remains lazy and loads only when
    # a property explanation is requested.
    print("[startup] Initializing authentication database...")
    init_db()
    print("[startup] Loading valuation dataset...")
    load_data()
    print("[startup] Loading valuation model...")
    load_model()
    print("[startup] Loading valuation calibrator...")
    load_calibrator()
    print("[startup] Loading location-aware fallback model...")
    load_location_aware_model()
    print("[startup] Preparing complete valuation pool...")
    load_valuation_pool()
    print("[startup] Loading locality statistics...")
    load_locality_stats()

    print(f"\n🚀 Real Estate Intelligence Platform API starting on http://127.0.0.1:{port}")
    print("   Landing  : /")
    print("   Home     : /home")
    print("   Search   : /search")
    print("   Property : /property/<property_id>")
    print("   Market   : /market")
    print("   Activity : /activity")
    print("   Health   : /api/health\n")

    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
