"""Tests for the learning, forecast, simulation and assistant code. None of these need a database."""
import os
from datetime import date, datetime, timedelta

import pytest

from core import assistant, learning, simulation


# ---------------- learning from offer outcomes

def test_unknown_ngo_starts_at_fifty_percent_and_moves_with_evidence():
    assert learning.acceptance_probability(0, 0) == 0.5
    assert learning.acceptance_probability(10, 10) == pytest.approx(12 / 14)
    assert learning.acceptance_probability(0, 10) == pytest.approx(2 / 14)
    assert learning.acceptance_probability(1, 1) < learning.acceptance_probability(10, 10)  # one success proves little


def test_an_ngo_that_never_answers_has_a_longer_expected_wait():
    reliable = learning.NgoHistory(accepted=9, declined=1, accept_minutes=27, fail_minutes=3)
    silent = learning.NgoHistory(expired=10, fail_minutes=150)
    unknown = learning.NgoHistory()
    wait = lambda h: learning.expected_wait_minutes(h, timeout_min=15)
    assert wait(reliable) < wait(unknown) < wait(silent)
    assert learning.wait_penalty_km(10) == 5.0


def test_two_ngos_with_no_history_get_the_same_penalty():
    a, b = learning.NgoHistory(), learning.NgoHistory()
    assert learning.expected_wait_minutes(a, 15) == learning.expected_wait_minutes(b, 15)


# ---------------- forecast

def weekly(values_by_age):
    today = datetime(2026, 11, 20, 21)
    return [(today - timedelta(days=age), meals) for age, meals in values_by_age]


def test_days_without_donations_count_as_zero():
    rows = weekly([(5, 100), (1, 100)])  # donations on 15 and 19 November
    days, y = learning.daily_totals(rows, date(2026, 11, 20))
    assert len(days) == 6 and list(y) == [100.0, 0.0, 0.0, 0.0, 100.0, 0.0]  # 20 November had none


def test_weekday_forecast_averages_the_same_weekday_and_gives_a_range():
    rows = weekly([(7, 120), (14, 140), (21, 160)])
    f = learning.weekday_forecast(rows, date(2026, 11, 20) + timedelta(days=0), as_of=date(2026, 11, 19))
    assert f["expected"] == 140 and f["days"] == 3
    assert round(f["low"], 1) == 114.4 and round(f["high"], 1) == 165.6
    assert f["basis"].startswith("same weekday")


def test_forecast_refuses_to_guess_from_too_little_history():
    assert learning.weekday_forecast(weekly([(1, 50), (2, 60)]), date(2026, 11, 21)) is None
    assert learning.backtest(weekly([(1, 50), (2, 60)]), date(2026, 11, 20)) is None


def test_backtest_compares_against_the_overall_average():
    # Weekends are twice as busy, so a weekday-aware forecast should beat "every day looks the same".
    rows = []
    for age in range(1, 57):
        d = datetime(2026, 11, 20, 21) - timedelta(days=age)
        rows.append((d, 160 if d.weekday() >= 5 else 80))
    bt = learning.backtest(rows, date(2026, 11, 20))
    assert bt["days_tested"] >= 5 and bt["mae_weekday"] < bt["mae_naive"] and bt["improvement_pct"] > 0


# ---------------- simulation

def test_learning_waits_less_on_average_than_distance_only():
    fixed = learned = 0.0
    for seed in range(1, 6):
        r = simulation.simulate(seed=seed)
        fixed += r["fixed"]["mean_minutes"]
        learned += r["learning"]["mean_minutes"]
    assert learned < fixed


def test_simulation_is_repeatable_and_reports_its_assumptions():
    a, b = simulation.simulate(seed=3), simulation.simulate(seed=3)
    assert a["fixed"] == b["fixed"] and a["learning"] == b["learning"]
    assert a["assumptions"]["listings"] == 400 and len(a["curve"]) == 4


# ---------------- language-model assistant (validation only; no network)

def test_assistant_keeps_valid_values_and_drops_bad_ones():
    reply = '```json\n{"title": "Veg pulao", "category": "Cooked meal (rice, curry, etc.)", "veg": true, "quantity_meals": 40, ' \
            '"cooked_time": "20:15", "temperature_c": 70, "notes": null}\n```'
    v = assistant.parse_response(reply)
    assert v["title"] == "Veg pulao" and v["quantity_meals"] == 40 and v["veg"] is True
    assert (v["cooked_time"].hour, v["cooked_time"].minute) == (20, 15) and v["temperature_c"] == 70.0 and "notes" not in v

    bad = assistant.validate({"title": "x", "category": "Rocket fuel", "quantity_meals": 10 ** 9, "cooked_time": "25:99",
                              "temperature_c": 999, "veg": "yes"})
    assert bad == {"title": "x"}


def test_assistant_fails_safely():
    with pytest.raises(assistant.AssistantError):
        assistant.parse_response("Sorry, I cannot help with that.")
    with pytest.raises(assistant.AssistantError):
        assistant.parse_response('{"category": "Rocket fuel"}')  # nothing usable
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        assert assistant.available() is False
        with pytest.raises(assistant.AssistantError):
            assistant.parse_listing_text("40 plates of biryani")
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved
