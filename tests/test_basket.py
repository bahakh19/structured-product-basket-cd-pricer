import numpy as np
import pytest

from notebook_code import load_definitions

nb = load_definitions(3)  # imports, inputs, curve, simulation, payoff and risk functions
L = nb['find_good_fit_cov_mat'](nb['corr_matrix'], nb['implied_vols'])


def price(**kw):
    args = dict(S0=nb['spot_prices'], sigma=nb['implied_vols'], r=nb['r'], valuation_dates=nb['valuation_dates'],
                payment_dates=nb['payment_dates'], L=L, num_paths=20000, seed=3)
    args.update(kw)
    return nb['compute_monte_carlo_price'](**args)


def test_swaps_reprice_at_par():
    zc, curve = nb['construct_zc_curve'](return_bootstrap=True)
    z = {1: float(zc(1.0))}
    z.update({int(n): float(v) for n, v in zip(curve.df_long['Time_to_Maturity'], curve.df_long['ZC'])})
    for n, s in zip(curve.df_long['Time_to_Maturity'], curve.df_long['Rate']):
        pv = sum(100 * s / (1 + z[j]) ** j for j in range(1, n)) + 100 * (1 + s) / (1 + z[n]) ** n
        assert pv == pytest.approx(100, abs=1e-9)


def test_futures_strip_is_chained():
    zc, curve = nb['construct_zc_curve'](return_bootstrap=True)
    m = curve.df_medium
    assert not m['ZC'].isna().any() and len(m) == 7  # the 8th futures has no following date
    for i in range(1, len(m)):
        growth = (1 + m.loc[i, 'ZC']) ** (m.loc[i, 'Time_to_Maturity'] / 365) / (1 + m.loc[i - 1, 'ZC']) ** (m.loc[i - 1, 'Time_to_Maturity'] / 365)
        assert growth == pytest.approx(1 + m.loc[i, 'Rate'] * (m.loc[i, 'Time_to_Maturity'] - m.loc[i - 1, 'Time_to_Maturity']) / 360)


def test_discount_factors_decrease_and_rate_bump_lowers_them():
    zc = nb['construct_zc_curve']()
    zc_up = nb['construct_zc_curve'](rate_bump=0.001)
    t = np.linspace(0.1, 7.5, 30)
    df = (1 + zc(t)) ** (-t)
    assert np.all(np.diff(df) < 0)
    assert np.all((1 + zc_up(t)) ** (-t) < df)


def test_cholesky_is_a_valid_factor():
    cov = L @ L.T
    assert np.allclose(np.sqrt(np.diag(cov)), nb['implied_vols'], atol=2e-3)
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    assert np.abs(corr - nb['corr_matrix']).max() < 0.01  # the nearest positive definite matrix is very close


def test_simulation_is_risk_neutral_with_the_input_vols_and_correlations():
    q = np.linspace(0, 0.05, 9)
    S = nb['simulate_gbm_paths'](nb['spot_prices'], nb['implied_vols'], nb['r'], nb['valuation_dates'], L, num_paths=200000, seed=1, dividend_yields=q)
    t = np.array([(d - nb['trade_date']).days for d in nb['valuation_dates']]) / 365
    fwd = nb['spot_prices'] * np.exp((nb['r'] - q) * t[-1])
    se = S[:, -1, :].std(axis=0) / np.sqrt(len(S))
    assert np.all(np.abs(S[:, -1, :].mean(axis=0) - fwd) < 4 * se)
    lr = np.log(S[:, 1, :] / S[:, 0, :])
    assert np.allclose(lr.std(axis=0) / np.sqrt(t[0]), nb['implied_vols'], rtol=0.01)
    assert np.abs(np.corrcoef(lr.T) - nb['corr_matrix']).max() < 0.02


def test_coupon_formula_on_known_prices():
    s0 = np.array([100.0, 100.0, 100.0])
    S = np.zeros((4, 2, 3))
    S[:, 0, :] = s0
    S[0, 1] = [110, 100, 120]  # all at or above: 6.25%
    S[1, 1] = [50, 100, 100]   # -30% floor, +6.25, +6.25: average -5.83% -> 0
    S[2, 1] = [97, 110, 110]   # -3%, +6.25, +6.25: 3.1667%
    S[3, 1] = [60, 60, 60]     # all floored: 0
    coupons = nb['compute_payoff'](S, [None], principal=100, cap_rate=0.0625, floor_rate=-0.30)[:, 0]
    np.testing.assert_allclose(coupons, [6.25, 0.0, (6.25 * 2 - 3) / 3, 0.0])


def test_zero_volatility_limit_pays_every_capped_coupon():
    p = price(sigma=np.full(9, 1e-10), num_paths=10)
    zc = nb['construct_zc_curve']()
    tp = np.array([(d - nb['trade_date']).days for d in nb['payment_dates']]) / 365
    ts = (nb['settlement_date'] - nb['trade_date']).days / 365
    df = (1 + zc(tp)) ** (-tp) / (1 + zc(ts)) ** (-ts)
    assert p == pytest.approx(6.25 * df.sum() + 100 * df[-1], rel=1e-10)


def test_common_random_numbers_and_fixed_initial_prices():
    base = price()
    assert price() == base
    up = nb['spot_prices'] * np.r_[1.01, np.ones(8)]
    assert price(S0=up) == pytest.approx(base, abs=1e-10)  # initial prices moving with the spot: no sensitivity
    assert price(S0=up, initial_prices=nb['spot_prices']) > base  # initial prices fixed: the CD is long the stocks


def test_risk_signs():
    base = price()
    assert price(sigma=nb['implied_vols'] * 1.2) < base       # short volatility
    assert price(rate_bump=0.001) < base                      # long rates exposure of a bond
    assert price(dividend_yields=np.full(9, 0.03)) < base     # dividends lower the coupons
