"""Does learning from offer outcomes help? A transparent simulation.

Every NGO has hidden behaviour (how often it stays silent, how often it accepts when it does respond, how
quickly). Two policies face exactly the same random outcomes for exactly the same listings:

  fixed     asks the NGOs in order of distance, always
  learning  adds a penalty for NGOs that tend to waste time, learned only from what it has seen so far

The numbers are synthetic. They show whether the idea works under stated assumptions; they are not
evidence about real NGOs.
"""
from __future__ import annotations

import random
import statistics

from core import learning


def _outcomes(rng: random.Random, ngos: list[dict], timeout: float) -> list[tuple[str, float]]:
    """For one listing: what each NGO would do if asked. ('silent'|'declined'|'accepted', minutes taken)."""
    out = []
    for n in ngos:
        if rng.random() < n["p_silent"]:
            out.append(("silent", timeout))
            continue
        minutes = min(timeout, rng.expovariate(1 / n["resp_mean"]))
        out.append(("accepted" if rng.random() < n["p_accept"] else "declined", minutes))
    return out


def _run(policy: str, listings: list[dict], ngos: list[dict], timeout: float) -> list[dict]:
    history = {i: learning.NgoHistory() for i in range(len(ngos))}
    results = []
    for L in listings:
        scores = []
        for i in range(len(ngos)):
            s = L["dist"][i]
            if policy == "learning":
                s += learning.wait_penalty_km(learning.expected_wait_minutes(history[i], timeout))
            scores.append((s, i))
        waited, claimed, asked = 0.0, False, 0
        for _s, i in sorted(scores):
            kind, minutes = L["outcome"][i]
            asked += 1
            h = history[i]
            if kind == "accepted":
                waited += minutes
                h.accepted += 1
                h.accept_minutes += minutes
                claimed = True
                break
            waited += minutes
            h.declined += kind == "declined"
            h.expired += kind == "silent"
            h.fail_minutes += minutes
        results.append({"minutes": waited, "first_try": claimed and asked == 1, "claimed": claimed})
    return results


def _summary(results: list[dict]) -> dict:
    minutes = sorted(r["minutes"] for r in results)
    return {
        "mean_minutes": statistics.mean(minutes),
        "p90_minutes": minutes[int(0.9 * (len(minutes) - 1))],
        "first_offer_accepted": sum(r["first_try"] for r in results) / len(results),
        "fell_through": sum(not r["claimed"] for r in results) / len(results),
    }


def simulate(n_listings: int = 400, n_ngos: int = 6, timeout_min: float = 15.0, seed: int = 1) -> dict:
    rng = random.Random(seed)
    ngos = [{"p_silent": rng.uniform(0.05, 0.6), "p_accept": rng.uniform(0.5, 0.95), "resp_mean": rng.uniform(1.5, 8.0)}
            for _ in range(n_ngos)]
    listings = [{"dist": [rng.uniform(0.5, 12.0) for _ in range(n_ngos)], "outcome": _outcomes(rng, ngos, timeout_min)}
                for _ in range(n_listings)]
    fixed = _run("fixed", listings, ngos, timeout_min)
    learned = _run("learning", listings, ngos, timeout_min)
    block = max(n_listings // 4, 1)
    curve = [{"listings": f"{i + 1}-{i + block}",
              "fixed": statistics.mean(r["minutes"] for r in fixed[i:i + block]),
              "learning": statistics.mean(r["minutes"] for r in learned[i:i + block])}
             for i in range(0, n_listings - block + 1, block)]
    return {"fixed": _summary(fixed), "learning": _summary(learned), "curve": curve,
            "assumptions": {"listings": n_listings, "ngos": n_ngos, "timeout_min": timeout_min, "seed": seed}}
