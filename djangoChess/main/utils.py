def calculate_elo(rating_a, rating_b, score_a, k_factor=32):
    """
    score_a: 1 for win, 0.5 for draw, 0 for loss
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    new_rating_a = rating_a + k_factor * (score_a - expected_a)
    return round(new_rating_a)
