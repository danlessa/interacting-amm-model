# %%
# Dependences
from pandas import DataFrame
from pandas.core.series import Series
import numpy as np

DEFAULT_SWAP = 100

# %% 
# KPI Definitions

def normalize(x: np.array) -> np.array:
    return (x - np.mean(x)) / np.std(x)

def slippage(balance_in: float,
             balance_out: float,
             amount_in: float,
             fee: float = 0.003) -> float:
    """
    Reference: 
    Balancer Whitepaper for W_i = W_f and fee = 0.03
    """
    spot_price = (balance_in / balance_out) * (1 / (1 - fee))
    amount_out_share = (1 - (balance_in / (balance_in + amount_in)))
    amount_out = balance_out * amount_out_share
    effective_price = amount_in / amount_out
    slippage = effective_price / spot_price - 1
    return slippage


def normalized_slippage(reserve_1: float,
                        reserve_2: float,
                        amount_1: float) -> float:
    slippage_1 = slippage(reserve_1, reserve_2, amount_1)
    amount_2 = amount_1 * reserve_2 / reserve_1
    slippage_2 = slippage(reserve_2, reserve_1, amount_2)
    norm_slippage = (slippage_1 + slippage_2) / 2
    return norm_slippage


def transaction_fees(reserve_1_series: Series,
                     reserve_2_series: Series,
                     fee=0.003,
                     return_token_1=True) -> Series:
    # Get the difference between reserves
    delta_reserve_1 = reserve_1_series.diff()
    delta_reserve_2 = reserve_2_series.diff()

    # Use parity to determine events
    parity = delta_reserve_1 * delta_reserve_2
    swaps = (parity < 0)
    mint_burns_skips = (parity >= 0)

    # Decide on what unit the yield will be
    if return_token_1 == True:
        tx_fees = delta_reserve_1.copy()
    else:
        tx_fees = delta_reserve_2.copy()

    # Retrieve tx fees according to swaps
    tx_fees[swaps] = tx_fees[swaps].abs() * fee
    tx_fees[mint_burns_skips] = 0.0

    return tx_fees


def kpi_price_volatility(df: DataFrame) -> float:
    WINDOW_SIZE: int = int(np.round(len(df) * 0.05))
    s = df.amm_price
    rolling_std = s.rolling(WINDOW_SIZE).std()
    rolling_mean = s.rolling(WINDOW_SIZE).mean()
    y = rolling_std / rolling_mean
    kpi = np.median(y.dropna())
    return kpi


def kpi_price_integral_error(df: DataFrame) -> float:
    s = np.abs(df.amm_price - df.market_price)
    kpi = s.sum() / (len(s) * df.market_price.mean())
    return kpi


def kpi_slippage_magnitude(df: DataFrame) -> float:
    s = normalized_slippage(df.uniswap_reserve_token_1,
                            df.uniswap_reserve_token_2,
                            DEFAULT_SWAP)
    kpi = s.mean()
    return kpi


def kpi_slippage_volatility(df: DataFrame) -> float:
    s = normalized_slippage(df.uniswap_reserve_token_1,
                            df.uniswap_reserve_token_2,
                            DEFAULT_SWAP)
    kpi = s.std().mean()
    return kpi


def kpi_immediate_yield(df: DataFrame) -> float:
    WINDOW_SIZE: int = int(np.round(len(df) * 0.01))
    fees = transaction_fees(df.uniswap_reserve_token_1,
                            df.uniswap_reserve_token_2)
    liquidity = df.uniswap_reserve_token_1
    yields = fees.rolling(WINDOW_SIZE).sum()
    yields /= (len(df) * liquidity.rolling(WINDOW_SIZE).mean())
    kpi = np.median(yields.dropna())
    return kpi


def kpi_integral_yield(df: DataFrame) -> float:
    WINDOW_SIZE: int = int(np.round(len(df) * 0.01))
    fees = transaction_fees(df.uniswap_reserve_token_1,
                            df.uniswap_reserve_token_2)
    liquidity = df.uniswap_reserve_token_1
    yields = fees.sum()
    yields /= liquidity.mean()
    kpi = yields
    return kpi

KPIs = {
    'price_volatility': kpi_price_volatility,
    'price_integral_error': kpi_price_integral_error,
    'slippage_magnitude': kpi_slippage_magnitude,
    'slippage_volatility': kpi_slippage_volatility,
    'immediate_yield': kpi_immediate_yield,
    'integral_yield': kpi_integral_yield
}


# %%
# Goals definitions


def goal_price_reliability(kpis: dict) -> float:
    y = normalize(kpis['price_volatility'])
    y += normalize(kpis['price_integral_error'])
    y /= 2
    return y


def goal_trade_xp(kpis: dict) -> float:
    y = normalize(kpis['slippage_magnitude'])
    y += normalize(kpis['slippage_volatility'])
    y /= 2
    return y


def goal_provider_xp(kpis: dict) -> float:
    y = normalize(kpis['immediate_yield'])
    y += normalize(kpis['integral_yield'])
    y /= 2
    return y

def goal_combined(goals: list) -> float:
    y = goals[0] + goals[1] + goals[2]
    return y

SYSTEM_GOALS = {
    'price_reliability': goal_price_reliability,
    'trade_xp': goal_trade_xp,
    'provider_xp': goal_provider_xp,
    'combined': goal_combined
}