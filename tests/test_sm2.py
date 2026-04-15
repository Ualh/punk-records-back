from src.sm2 import sm2


def test_sm2_successful_review_progression() -> None:
    interval, ease, reps, _ = sm2(quality=5, repetitions=2, ease_factor=2.5, interval=6)
    assert interval == 15
    assert round(ease, 1) == 2.6
    assert reps == 3


def test_sm2_reset_on_low_quality() -> None:
    interval, ease, reps, _ = sm2(quality=2, repetitions=4, ease_factor=2.5, interval=20)
    assert interval == 1
    assert reps == 0
    assert ease >= 1.3
