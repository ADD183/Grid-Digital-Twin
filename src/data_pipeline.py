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


def fetch_open_meteo_solar_data(
    latitude: float = PUNE_LAT,
    longitude: float = PUNE_LON,
    start_date: str = "2023-01-01",
    end_date: str = "2023-01-31",
) -> pd.DataFrame:
    """
    Fetch high-resolution hourly solar irradiance (shortwave_radiation in W/m2) from Open-Meteo API.
    Supports historical archive and live forecast endpoints.
    """
    import httpx
    
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    now_dt = pd.Timestamp.now()
    
    if end_dt > now_dt - pd.Timedelta(days=5):
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}&"
            f"hourly=shortwave_radiation,direct_normal_irradiance&forecast_days=7"
        )
    else:
        url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={latitude}&longitude={longitude}&"
            f"start_date={start_dt.strftime('%Y-%m-%d')}&"
            f"end_date={end_dt.strftime('%Y-%m-%d')}&"
            f"hourly=shortwave_radiation"
        )

    headers = {"User-Agent": "VoltPredict/1.0"}
    with httpx.Client(timeout=10.0, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    ghi = hourly.get("shortwave_radiation", [])

    df = pd.DataFrame({"ghi": ghi}, index=pd.to_datetime(times))
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def fetch_pune_solar_data(
    start_date: str = "2023-01-01",
    end_date: str = "2023-01-31",
    freq: str = "15min",
    cache_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Fetch solar irradiance data for Pune (PVGIS or Open-Meteo hourly, or 15-min sub-hourly synthetic).
    Caches the response to CSV to prevent unnecessary re-fetching.
    
    Args:
        start_date (str): Start date ISO string.
        end_date (str): End date ISO string.
        freq (str): Time frequency (e.g. '15min', 'h').
        cache_path (Optional[str]): File path for local cache.
        
    Returns:
        pd.DataFrame: DataFrame indexed by timestamp with solar generation metrics.
    """
    ensure_directories()
    if cache_path is None:
        cache_path = os.path.join(RAW_DATA_DIR, f"pvgis_solar_pune_{freq.replace(':', '_')}.csv")

    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df

    time_index = pd.date_range(start=start_date, end=end_date, freq=freq)

    # Multi-tier Data Provider Ladder:
    # 1. Local Cache -> 2. PVGIS JRC -> 3. Open-Meteo API -> 4. Physical Clear-Sky Model
    try:
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
        
        if "G(h)" in data.columns:
            ghi = data["G(h)"]
        elif "ghi" in data.columns:
            ghi = data["ghi"]
        else:
            ghi = data.iloc[:, 0]
            
        df_hourly = pd.DataFrame({"ghi": ghi}, index=data.index)
        if df_hourly.index.tz is not None:
            df_hourly.index = df_hourly.index.tz_localize(None)

    except Exception as pvgis_err:
        print(f"[Info] PVGIS unreachable ({pvgis_err}). Querying Open-Meteo Solar API for Pune...")
        try:
            df_hourly = fetch_open_meteo_solar_data(PUNE_LAT, PUNE_LON, start_date, end_date)
        except Exception as om_err:
            print(f"[Warning] Open-Meteo unreachable ({om_err}). Using physical clear-sky model for Pune.")
            df_hourly = _generate_fallback_solar(time_index)

    # Resample / reindex to requested frequency with stochastic sub-hourly variability
    if freq in ["15min", "15T"]:
        df = stochastic_subhourly_solar(df_hourly, time_index)
    else:
        reindexed = df_hourly["ghi"].reindex(time_index.union(df_hourly.index)).interpolate(method="time")
        ghi_vals = reindexed.reindex(time_index).ffill().bfill().values
        solar_pu = np.clip(ghi_vals / 1000.0, 0.0, 1.0)
        df = pd.DataFrame({
            "ghi": ghi_vals,
            "solar_pu": solar_pu,
            "solar_lower_pu": np.maximum(0.0, solar_pu - 0.05),
            "solar_upper_pu": np.minimum(1.0, solar_pu + 0.05),
        }, index=time_index)

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df.to_csv(cache_path)
    return df



def stochastic_subhourly_solar(
    hourly_df: pd.DataFrame,
    target_index: pd.DatetimeIndex,
    noise_std: float = 0.04,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Interpolate hourly solar irradiance to 15-minute intervals with stochastic sub-hourly
    variability and explicit uncertainty bounds (90% confidence interval).
    """
    rng = np.random.default_rng(seed)
    reindexed = hourly_df["ghi"].reindex(target_index.union(hourly_df.index)).interpolate(method="time")
    subhourly_ghi = reindexed.reindex(target_index).ffill().bfill().values

    # Add stochastic cloud passing variation
    hour = target_index.hour + target_index.minute / 60.0
    day_mask = (hour >= 6.0) & (hour <= 18.5)
    noise = rng.normal(loc=0.0, scale=noise_std, size=len(target_index))
    
    stochastic_factor = np.ones(len(target_index))
    stochastic_factor[day_mask] = np.clip(1.0 + noise[day_mask], 0.6, 1.25)
    
    ghi = np.maximum(0.0, subhourly_ghi * stochastic_factor)
    solar_pu = np.clip(ghi / 1000.0, 0.0, 1.0)
    
    # Explicit 90% uncertainty bounds (+/- 1.645 * std)
    uncertainty_margin = np.where(day_mask, 1.645 * noise_std * (subhourly_ghi / 1000.0), 0.0)
    solar_lower_pu = np.clip(solar_pu - uncertainty_margin, 0.0, 1.0)
    solar_upper_pu = np.clip(solar_pu + uncertainty_margin, 0.0, 1.0)

    return pd.DataFrame({
        "ghi": ghi,
        "solar_pu": solar_pu,
        "solar_lower_pu": solar_lower_pu,
        "solar_upper_pu": solar_upper_pu,
    }, index=target_index)


def generate_synthetic_load_profile(
    time_index: pd.DatetimeIndex,
    base_kw: float = 100.0,
    peak_kw: float = 250.0,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic customer load profile with documented diurnal pattern and explicit uncertainty bounds.
    Supports native 15-minute and hourly resolutions.
    """
    rng = np.random.default_rng(seed)
    hours = time_index.hour + time_index.minute / 60.0

    # Diurnal shape interpolation
    hour_anchors = np.arange(24)
    diurnal_anchors = np.array([
        0.30, 0.28, 0.25, 0.25, 0.28, 0.35,  # 00-05: Overnight trough
        0.55, 0.75, 0.80, 0.70, 0.65, 0.60,  # 06-11: Morning ramp
        0.60, 0.62, 0.65, 0.70, 0.80, 0.95,  # 12-17: Midday to early evening
        1.00, 0.98, 0.90, 0.75, 0.55, 0.40   # 18-23: Evening peak & drop
    ])
    
    base_profile = np.interp(hours, hour_anchors, diurnal_anchors, period=24)
    noise_sigma = 0.04
    noise = rng.normal(loc=0.0, scale=noise_sigma, size=len(time_index))
    noisy_profile = np.clip(base_profile + noise, 0.15, 1.10)

    load_kw = base_kw + (peak_kw - base_kw) * noisy_profile
    load_pu = load_kw / peak_kw

    # 90% confidence uncertainty bounds
    bound_delta = 1.645 * noise_sigma * ((peak_kw - base_kw) / peak_kw)
    load_lower_pu = np.clip(load_pu - bound_delta, 0.10, 1.10)
    load_upper_pu = np.clip(load_pu + bound_delta, 0.10, 1.10)

    return pd.DataFrame({
        "load_kw": load_kw,
        "load_pu": load_pu,
        "load_lower_pu": load_lower_pu,
        "load_upper_pu": load_upper_pu,
    }, index=time_index)


def build_aligned_dataset(
    start_date: str = "2023-01-01",
    end_date: str = "2023-01-31",
    freq: str = "h",
    output_path: str = DEFAULT_ALIGNED_OUTPUT
) -> pd.DataFrame:
    """
    Combine solar generation data and synthetic load profile into a time-aligned DataFrame.
    """
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)
    if end_ts < start_ts:
        raise ValueError(f"Invalid date range: start_date '{start_date}' is later than end_date '{end_date}'.")

    ensure_directories()

    time_index = pd.date_range(start=start_date, end=end_date, freq=freq)
    solar_df = fetch_pune_solar_data(start_date=start_date, end_date=end_date, freq=freq)
    if hasattr(solar_df.index, "tz") and solar_df.index.tz is not None:
        solar_df.index = solar_df.index.tz_localize(None)
    
    load_df = generate_synthetic_load_profile(time_index=time_index)

    if len(solar_df) != len(load_df):
        solar_df = solar_df.reindex(load_df.index, method="ffill").bfill()

    aligned_df = pd.DataFrame({
        "solar_ghi": solar_df["ghi"].values,
        "solar_pu": solar_df["solar_pu"].values,
        "solar_lower_pu": solar_df.get("solar_lower_pu", np.maximum(0.0, solar_df["solar_pu"] - 0.05)).values,
        "solar_upper_pu": solar_df.get("solar_upper_pu", np.minimum(1.0, solar_df["solar_pu"] + 0.05)).values,
        "load_kw": load_df["load_kw"].values,
        "load_pu": load_df["load_pu"].values,
        "load_lower_pu": load_df.get("load_lower_pu", np.maximum(0.1, load_df["load_pu"] - 0.05)).values,
        "load_upper_pu": load_df.get("load_upper_pu", np.minimum(1.1, load_df["load_pu"] + 0.05)).values,
    }, index=load_df.index)

    aligned_df.to_csv(output_path)
    return aligned_df

