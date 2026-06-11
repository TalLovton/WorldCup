import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


def _dc_correction(home_goals: int, away_goals: int, mu_h: float, mu_a: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1 - mu_h * mu_a * rho
    if home_goals == 1 and away_goals == 0:
        return 1 + mu_a * rho
    if home_goals == 0 and away_goals == 1:
        return 1 + mu_h * rho
    if home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1.0


def _neg_log_likelihood(params: np.ndarray, teams: list[str], matches: list[dict]) -> float:
    n = len(teams)
    idx = {t: i for i, t in enumerate(teams)}
    attack = params[:n]
    defence = params[n : 2 * n]
    home_adv = params[2 * n]
    rho = params[2 * n + 1]

    ll = 0.0
    for m in matches:
        hi = idx.get(m["home"])
        ai = idx.get(m["away"])
        if hi is None or ai is None:
            continue
        mu_h = math.exp(attack[hi] - defence[ai] + home_adv)
        mu_a = math.exp(attack[ai] - defence[hi])
        correction = _dc_correction(m["home_goals"], m["away_goals"], mu_h, mu_a, rho)
        if correction <= 0:
            return 1e9
        ll += (
            poisson.logpmf(m["home_goals"], mu_h)
            + poisson.logpmf(m["away_goals"], mu_a)
            + math.log(correction)
        )
    return -ll


def fit(matches: list[dict]) -> dict:
    teams = sorted({m["home"] for m in matches} | {m["away"] for m in matches})
    n = len(teams)
    if n < 2:
        return {}

    x0 = np.zeros(2 * n + 2)
    x0[2 * n] = 0.3   # home advantage
    x0[2 * n + 1] = -0.1  # rho

    result = minimize(
        _neg_log_likelihood,
        x0,
        args=(teams, matches),
        method="L-BFGS-B",
        options={"maxiter": 1000, "ftol": 1e-9},
    )

    params = result.x
    idx = {t: i for i, t in enumerate(teams)}
    return {
        "teams": teams,
        "attack": {t: params[idx[t]] for t in teams},
        "defence": {t: params[n + idx[t]] for t in teams},
        "home_adv": params[2 * n],
        "rho": params[2 * n + 1],
    }


def predict(home: str, away: str, model_params: dict, max_goals: int = 8) -> dict:
    if not model_params:
        return {
            "home_win": 1 / 3,
            "draw": 1 / 3,
            "away_win": 1 / 3,
            "most_likely_score": "N/A",
            "score_probs": {},
            "clean_sheet_home": None,
            "clean_sheet_away": None,
            "note": "Insufficient history — uniform prior used.",
        }

    atk = model_params["attack"]
    dfc = model_params["defence"]
    ha = model_params["home_adv"]
    rho = model_params["rho"]

    avg_atk = sum(atk.values()) / len(atk)
    avg_dfc = sum(dfc.values()) / len(dfc)

    home_atk = atk.get(home, avg_atk)
    home_dfc = dfc.get(home, avg_dfc)
    away_atk = atk.get(away, avg_atk)
    away_dfc = dfc.get(away, avg_dfc)

    note = ""
    unknown = [t for t in (home, away) if t not in atk]
    if unknown:
        note = f"No history for {', '.join(unknown)} — average ratings used."

    mu_h = math.exp(home_atk - away_dfc + ha)
    mu_a = math.exp(away_atk - home_dfc)

    score_matrix = np.zeros((max_goals + 1, max_goals + 1))
    for hg in range(max_goals + 1):
        for ag in range(max_goals + 1):
            p = poisson.pmf(hg, mu_h) * poisson.pmf(ag, mu_a)
            p *= _dc_correction(hg, ag, mu_h, mu_a, rho)
            score_matrix[hg, ag] = max(p, 0.0)

    # normalise
    total = score_matrix.sum()
    if total > 0:
        score_matrix /= total

    home_win = float(np.tril(score_matrix, -1).sum())
    draw = float(np.trace(score_matrix))
    away_win = float(np.triu(score_matrix, 1).sum())

    best_idx = np.unravel_index(score_matrix.argmax(), score_matrix.shape)
    most_likely = f"{best_idx[0]}-{best_idx[1]}"

    score_probs = {}
    for hg in range(min(5, max_goals + 1)):
        for ag in range(min(5, max_goals + 1)):
            p = score_matrix[hg, ag]
            if p >= 0.02:
                score_probs[f"{hg}-{ag}"] = round(p, 4)

    clean_sheet_home = float(score_matrix[:, 0].sum())
    clean_sheet_away = float(score_matrix[0, :].sum())

    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4),
        "most_likely_score": most_likely,
        "score_probs": score_probs,
        "clean_sheet_home": round(clean_sheet_home, 4),
        "clean_sheet_away": round(clean_sheet_away, 4),
        "note": note,
    }


if __name__ == "__main__":
    # Smoke-test with synthetic data
    synthetic = [
        {"home": "Brazil", "away": "Argentina", "home_goals": 2, "away_goals": 1},
        {"home": "Argentina", "away": "France", "home_goals": 1, "away_goals": 1},
        {"home": "France", "away": "Brazil", "home_goals": 0, "away_goals": 2},
        {"home": "Brazil", "away": "France", "home_goals": 3, "away_goals": 0},
        {"home": "Argentina", "away": "Brazil", "home_goals": 1, "away_goals": 2},
        {"home": "France", "away": "Argentina", "home_goals": 2, "away_goals": 2},
    ]
    params = fit(synthetic)
    result = predict("Brazil", "Argentina", params)
    total = result["home_win"] + result["draw"] + result["away_win"]
    print(f"Brazil vs Argentina: {result}")
    print(f"Probabilities sum: {total:.4f} (should be ~1.0)")
    assert abs(total - 1.0) < 0.02, "Probabilities don't sum to 1!"
    print("Smoke test passed.")
