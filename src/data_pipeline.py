"""
Data pipeline for fetching PVGIS solar data for Pune, India, generating synthetic load profiles,
and producing an aligned time-indexed dataset for grid power-flow simulations.
"""

import os
from typing import Optional, Tuple
import numpy as np
import pandas as pd
import pvlib

# Pune, India coordinates
PUNE_LAT = 18.52
PUNE_LON = 73.85

RAW_DATA_DIR = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")
DEFAULT_SOLAR_CACHE = os.path.join(RAW_DATA_DIR, "pvgis_solar_pune.csv")
DEFAULT_ALIGNED_OUTPUT = os.path.join(PROCESSED_DATA_DIR, "aligned_solar_load.csv")


def ensure_directories():
    """Ensure data storage directories exist."""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)


def _generate_fallback_solar(time_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Generate a realistic deterministic solar irradiance profile (W/m2) for Pune coordinates
    used if PVGIS web API is unreachable.
    """
    # Simple solar hour calculation
    hour = time_index.hour + time_index.minute / 60.0
    day_of_year = time_index.dayofyear
    
    # Solar declination angle approximation
    declination = 23.45 * np.sin(np.radians(360 / 365 * (day_of_year - 81)))
    
    # Solar zenith angle approximation for Pune (lat 18.52 N)
    lat_rad = np.radians(PUNE_LAT)
    dec_rad = np.radians(declination)
    hour_angle_rad = np.radians((hour - 12) * 15)
    
    cos_zenith = np.sin(lat_rad) * np.sin(dec_rad) + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_angle_rad)
    cos_zenith = np.maximum(0.0, cos_zenith)
    
    # Clear sky GHI approximation (W/m2)
    ghi = 1000.0 * (cos_zenith ** 1.2)
    
    df = pd.DataFrame({
        "ghi": ghi,
        "solar_pu": ghi / 1000.0
    }, index=time_index)
    return df


def fetch_pune_solar_data(
    start_date: str = "2023-01-01",
    end_date: str = "2023-01-31",
    cache_path: str = DEFAULT_SOLAR_CACHE
) -> pd.DataFrame:
    """
    Fetch hourly solar irradiance data for Pune via pvlib.iotools.get_pvgis_hourly.
    Caches the raw response to CSV to prevent unnecessary re-fetching.
    
    Args:
        start_date (str): Start date ISO string.
        end_date (str): End date ISO string.
        cache_path (str): File path for local cache.
        
    Returns:
        pd.DataFrame: DataFrame indexed by timestamp with solar generation metrics.
    """
    ensure_directories()

    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df

    time_index = pd.date_range(start=start_date, end=end_date, freq="h")

    try:
        # Request PVGIS hourly data
        # Note: PVGIS start year is usually prior years (e.g. 2020)
        start_year = pd.to_datetime(start_date).year
        end_year = pd.to_datetime(end_date).year
        
        res = pvlib.iotools.get_pvgis_hourly(
            latitude=PUNE_LAT,
            longitude=PUNE_LON,
            start=start_year,
            end=end_year,
            components=True
        )
        data = res[0]
        
        # Select GHI column
        if "G(h)" in data.columns:
            ghi = data["G(h)"]
        elif "ghi" in data.columns:
            ghi = data["ghi"]
        else:
            ghi = data.iloc[:, 0]
            
        df = pd.DataFrame({"ghi": ghi}, index=data.index)
        # Normalize to 0.0 - 1.0 p.u. (assuming 1000 W/m2 peak rating)
        df["solar_pu"] = (df["ghi"] / 1000.0).clip(lower=0.0, upper=1.0)
        
        # Ensure index is timezone naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Slice to requested date range if necessary
        df = df.loc[df.index >= time_index[0]]
        if len(df) == 0:
            df = _generate_fallback_solar(time_index)

    except Exception as err:
        print(f"[Warning] PVGIS fetch error: {err}. Using deterministic solar model for Pune.")
        df = _generate_fallback_solar(time_index)

    # Ensure tz-naive index on return
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df.to_csv(cache_path)
    return df


def generate_synthetic_load_profile(
    time_index: pd.DatetimeIndex,
    base_kw: float = 100.0,
    peak_kw: float = 250.0,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate an hourly synthetic customer load profile with documented diurnal pattern.
    - Overnight trough (00:00-05:00): ~30% peak
    - Morning ramp (06:00-09:00): ~70% peak
    - Midday plateau (10:00-16:00): ~65% peak
    - Evening peak (17:00-22:00): 100% peak
    - Night drop (23:00): ~40% peak
    
    Args:
        time_index (pd.DatetimeIndex): Target timestamp index.
        base_kw (float): Baseline demand in kW.
        peak_kw (float): Peak demand in kW.
        seed (int): Random seed for reproducibility.
        
    Returns:
        pd.DataFrame: DataFrame containing synthetic load profile in kW and p.u.
    """
    np.random.seed(seed)
    hours = time_index.hour

    # Define normalized shape by hour of day (0 to 23)
    diurnal_shape = np.array([
        0.30, 0.28, 0.25, 0.25, 0.28, 0.35,  # 00-05: Overnight trough
        0.55, 0.75, 0.80, 0.70, 0.65, 0.60,  # 06-11: Morning ramp
        0.60, 0.62, 0.65, 0.70, 0.80, 0.95,  # 12-17: Midday to early evening
        1.00, 0.98, 0.90, 0.75, 0.55, 0.40   # 18-23: Evening peak & drop
    ])

    base_profile = diurnal_shape[hours]
    # Add random Gaussian noise (5% std dev)
    noise = np.random.normal(loc=0.0, scale=0.04, size=len(time_index))
    noisy_profile = np.clip(base_profile + noise, 0.15, 1.10)

    load_kw = base_kw + (peak_kw - base_kw) * noisy_profile
    load_pu = load_kw / peak_kw

    df = pd.DataFrame({
        "load_kw": load_kw,
        "load_pu": load_pu
    }, index=time_index)

    return df


def build_aligned_dataset(
    start_date: str = "2023-01-01",
    end_date: str = "2023-01-31",
    output_path: str = DEFAULT_ALIGNED_OUTPUT
) -> pd.DataFrame:
    """
    Combine solar generation data and synthetic load profile into a time-aligned DataFrame.
    
    Args:
        start_date (str): Start date string.
        end_date (str): End date string.
        output_path (str): Output CSV destination.
        
    Returns:
        pd.DataFrame: Time-aligned dataset containing solar and load series.
    """
    ensure_directories()

    solar_df = fetch_pune_solar_data(start_date=start_date, end_date=end_date)
    if hasattr(solar_df.index, "tz") and solar_df.index.tz is not None:
        solar_df.index = solar_df.index.tz_localize(None)
    
    # Reindex time if solar_df index length differs
    time_index = pd.date_range(start=start_date, end=end_date, freq="h")
    load_df = generate_synthetic_load_profile(time_index=time_index)

    if len(solar_df) != len(load_df):
        solar_df = solar_df.reindex(load_df.index, method="ffill").bfill()

    aligned_df = pd.DataFrame({
        "solar_ghi": solar_df["ghi"].values,
        "solar_pu": solar_df["solar_pu"].values,
        "load_kw": load_df["load_kw"].values,
        "load_pu": load_df["load_pu"].values,
    }, index=load_df.index)

    aligned_df.to_csv(output_path)
    return aligned_df
