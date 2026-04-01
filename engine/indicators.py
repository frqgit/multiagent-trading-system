"""Indicator Library — vectorised technical indicators over numpy/pandas arrays.

All public functions accept a pandas Series (close, high, low, volume) and
return a pandas Series or DataFrame of the same length.  NaN-padded at the
start where the look-back window has not yet filled.

Usage:
    from engine.indicators import RSI, MACD, SMA, EMA, BollingerBands
    rsi_series = RSI(close, period=14)
    macd_df    = MACD(close)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "SMA", "EMA", "WMA", "HMA", "DEMA", "TEMA", "KAMA",
    "RSI", "StochRSI",
    "MACD",
    "BollingerBands",
    "ATR", "ADX",
    "Stochastic",
    "CCI", "WilliamsR", "MFI", "OBV", "VWAP",
    "SuperTrend",
    "IchimokuCloud",
    "DonchianChannel", "KeltnerChannel",
    "ParabolicSAR",
    "ROC", "Momentum",
    "CrossAbove", "CrossBelow",
]


# ---------------------------------------------------------------------------
# Moving Averages
# ---------------------------------------------------------------------------

def SMA(series: pd.Series, period: int = 20) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def EMA(series: pd.Series, period: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def WMA(series: pd.Series, period: int = 20) -> pd.Series:
    """Weighted Moving Average."""
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True,
    )


def HMA(series: pd.Series, period: int = 20) -> pd.Series:
    """Hull Moving Average — reduced lag."""
    half = WMA(series, period // 2)
    full = WMA(series, period)
    diff = 2 * half - full
    return WMA(diff, int(np.sqrt(period)))


def DEMA(series: pd.Series, period: int = 20) -> pd.Series:
    """Double Exponential Moving Average."""
    ema1 = EMA(series, period)
    ema2 = EMA(ema1, period)
    return 2 * ema1 - ema2


def TEMA(series: pd.Series, period: int = 20) -> pd.Series:
    """Triple Exponential Moving Average."""
    ema1 = EMA(series, period)
    ema2 = EMA(ema1, period)
    ema3 = EMA(ema2, period)
    return 3 * ema1 - 3 * ema2 + ema3


def KAMA(series: pd.Series, period: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    """Kaufman Adaptive Moving Average."""
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    direction = (series - series.shift(period)).abs()
    volatility = series.diff().abs().rolling(window=period).sum()
    er = direction / volatility.replace(0, np.nan)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    result = pd.Series(np.nan, index=series.index, dtype=float)
    result.iloc[period] = series.iloc[period]
    for i in range(period + 1, len(series)):
        if np.isnan(result.iloc[i - 1]):
            result.iloc[i] = series.iloc[i]
        else:
            result.iloc[i] = result.iloc[i - 1] + sc.iloc[i] * (series.iloc[i] - result.iloc[i - 1])
    return result


# ---------------------------------------------------------------------------
# Oscillators
# ---------------------------------------------------------------------------

def RSI(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder smoothing)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def StochRSI(series: pd.Series, rsi_period: int = 14, stoch_period: int = 14,
             k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    """Stochastic RSI — %K and %D lines."""
    rsi = RSI(series, rsi_period)
    lowest = rsi.rolling(stoch_period).min()
    highest = rsi.rolling(stoch_period).max()
    stoch_rsi = (rsi - lowest) / (highest - lowest).replace(0, np.nan)
    k = stoch_rsi.rolling(k_smooth).mean() * 100
    d = k.rolling(d_smooth).mean()
    return pd.DataFrame({"StochRSI_K": k, "StochRSI_D": d}, index=series.index)


def Stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Stochastic Oscillator — %K and %D."""
    lowest = low.rolling(k_period).min()
    highest = high.rolling(k_period).max()
    k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return pd.DataFrame({"Stoch_K": k, "Stoch_D": d}, index=close.index)


def CCI(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    return (tp - sma_tp) / (0.015 * mad).replace(0, np.nan)


def WilliamsR(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R."""
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    return -100 * (highest - close) / (highest - lowest).replace(0, np.nan)


def MFI(high: pd.Series, low: pd.Series, close: pd.Series,
        volume: pd.Series, period: int = 14) -> pd.Series:
    """Money Flow Index."""
    tp = (high + low + close) / 3
    raw_mf = tp * volume
    delta = tp.diff()
    pos_flow = raw_mf.where(delta > 0, 0.0).rolling(period).sum()
    neg_flow = raw_mf.where(delta <= 0, 0.0).rolling(period).sum()
    ratio = pos_flow / neg_flow.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def MACD(series: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> pd.DataFrame:
    """MACD — line, signal, and histogram."""
    ema_fast = EMA(series, fast)
    ema_slow = EMA(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "MACD": macd_line,
        "MACD_Signal": signal_line,
        "MACD_Hist": histogram,
    }, index=series.index)


# ---------------------------------------------------------------------------
# Bands & Channels
# ---------------------------------------------------------------------------

def BollingerBands(series: pd.Series, period: int = 20,
                   std_dev: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands — middle, upper, lower, %B, bandwidth."""
    middle = SMA(series, period)
    dev = series.rolling(period).std()
    upper = middle + std_dev * dev
    lower = middle - std_dev * dev
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    bandwidth = (upper - lower) / middle.replace(0, np.nan) * 100
    return pd.DataFrame({
        "BB_Middle": middle,
        "BB_Upper": upper,
        "BB_Lower": lower,
        "BB_PctB": pct_b,
        "BB_Bandwidth": bandwidth,
    }, index=series.index)


def DonchianChannel(high: pd.Series, low: pd.Series, period: int = 20) -> pd.DataFrame:
    """Donchian Channel — upper, lower, middle."""
    upper = high.rolling(period).max()
    lower = low.rolling(period).min()
    middle = (upper + lower) / 2
    return pd.DataFrame({"DC_Upper": upper, "DC_Lower": lower, "DC_Middle": middle},
                        index=high.index)


def KeltnerChannel(high: pd.Series, low: pd.Series, close: pd.Series,
                   ema_period: int = 20, atr_period: int = 10,
                   multiplier: float = 2.0) -> pd.DataFrame:
    """Keltner Channel — EMA ± ATR multiplier."""
    mid = EMA(close, ema_period)
    atr = ATR(high, low, close, atr_period)
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr
    return pd.DataFrame({"KC_Upper": upper, "KC_Middle": mid, "KC_Lower": lower},
                        index=close.index)


# ---------------------------------------------------------------------------
# Volatility & Trend
# ---------------------------------------------------------------------------

def ATR(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def ADX(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.DataFrame:
    """Average Directional Index — ADX, +DI, -DI."""
    atr = ATR(high, low, close, period)
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    plus_di = 100 * EMA(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100 * EMA(minus_dm, period) / atr.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = EMA(dx, period)

    return pd.DataFrame({"ADX": adx, "Plus_DI": plus_di, "Minus_DI": minus_di},
                        index=close.index)


def SuperTrend(high: pd.Series, low: pd.Series, close: pd.Series,
               period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """SuperTrend indicator — trend direction and line."""
    atr = ATR(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(np.nan, index=close.index, dtype=float)
    direction = pd.Series(1, index=close.index, dtype=int)  # 1=up, -1=down

    for i in range(period, len(close)):
        if close.iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif close.iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                lower_band.iloc[i] = lower_band.iloc[i - 1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                upper_band.iloc[i] = upper_band.iloc[i - 1]

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    return pd.DataFrame({"SuperTrend": supertrend, "ST_Direction": direction},
                        index=close.index)


def IchimokuCloud(high: pd.Series, low: pd.Series, close: pd.Series,
                  tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> pd.DataFrame:
    """Ichimoku Cloud — Tenkan, Kijun, Senkou A/B, Chikou."""
    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
    senkou_b_line = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(kijun)
    chikou = close.shift(-kijun)
    return pd.DataFrame({
        "Tenkan": tenkan_sen, "Kijun": kijun_sen,
        "Senkou_A": senkou_a, "Senkou_B": senkou_b_line,
        "Chikou": chikou,
    }, index=close.index)


def ParabolicSAR(high: pd.Series, low: pd.Series,
                 af_start: float = 0.02, af_step: float = 0.02,
                 af_max: float = 0.20) -> pd.Series:
    """Parabolic Stop and Reverse."""
    length = len(high)
    sar = pd.Series(np.nan, index=high.index, dtype=float)
    af = af_start
    is_long = True
    ep = low.iloc[0]
    sar.iloc[0] = high.iloc[0]

    for i in range(1, length):
        if is_long:
            sar.iloc[i] = sar.iloc[i - 1] + af * (ep - sar.iloc[i - 1])
            sar.iloc[i] = min(sar.iloc[i], low.iloc[i - 1],
                              low.iloc[i - 2] if i >= 2 else low.iloc[i - 1])
            if low.iloc[i] < sar.iloc[i]:
                is_long = False
                sar.iloc[i] = ep
                ep = low.iloc[i]
                af = af_start
            else:
                if high.iloc[i] > ep:
                    ep = high.iloc[i]
                    af = min(af + af_step, af_max)
        else:
            sar.iloc[i] = sar.iloc[i - 1] + af * (ep - sar.iloc[i - 1])
            sar.iloc[i] = max(sar.iloc[i], high.iloc[i - 1],
                              high.iloc[i - 2] if i >= 2 else high.iloc[i - 1])
            if high.iloc[i] > sar.iloc[i]:
                is_long = True
                sar.iloc[i] = ep
                ep = high.iloc[i]
                af = af_start
            else:
                if low.iloc[i] < ep:
                    ep = low.iloc[i]
                    af = min(af + af_step, af_max)
    return sar


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------

def OBV(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def VWAP(high: pd.Series, low: pd.Series, close: pd.Series,
         volume: pd.Series) -> pd.Series:
    """Volume Weighted Average Price (cumulative intraday)."""
    tp = (high + low + close) / 3
    cum_tp_vol = (tp * volume).cumsum()
    cum_vol = volume.cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------

def ROC(series: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change (percent)."""
    shifted = series.shift(period)
    return ((series - shifted) / shifted.replace(0, np.nan)) * 100


def Momentum(series: pd.Series, period: int = 10) -> pd.Series:
    """Momentum (price difference)."""
    return series - series.shift(period)


# ---------------------------------------------------------------------------
# Cross helpers
# ---------------------------------------------------------------------------

def CrossAbove(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """Boolean — True on bars where *a* crosses above *b*."""
    prev_a = series_a.shift(1)
    prev_b = series_b.shift(1)
    return (prev_a <= prev_b) & (series_a > series_b)


def CrossBelow(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """Boolean — True on bars where *a* crosses below *b*."""
    prev_a = series_a.shift(1)
    prev_b = series_b.shift(1)
    return (prev_a >= prev_b) & (series_a < series_b)
