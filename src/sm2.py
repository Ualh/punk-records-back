from datetime import datetime, timedelta


def sm2(
    quality: int,
    repetitions: int,
    ease_factor: float,
    interval: int,
) -> tuple[int, float, int, datetime]:
    """
    Apply SM-2 scheduling update and return new card values.

    quality: 0-5 score where values below 3 reset progress.
    """
    if quality < 0 or quality > 5:
        raise ValueError("quality must be between 0 and 5")

    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1

    # SM-2 keeps ease_factor >= 1.3 to prevent impossible schedules.
    ease_factor = max(
        1.3,
        ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
    )
    next_review = datetime.now() + timedelta(days=interval)

    return interval, ease_factor, repetitions, next_review
