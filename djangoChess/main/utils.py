from web3 import Web3


def calculate_elo(rating_a, rating_b, score_a, k_factor=32):
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    new_rating_a = rating_a + k_factor * (score_a - expected_a)
    return round(new_rating_a)


def normalize_ethereum_address(address: str) -> str | None:
    if not address:
        return None
    value = address.strip()
    if not Web3.is_address(value):
        return None
    return Web3.to_checksum_address(value)
