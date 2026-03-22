import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Pairing:
    white_seed: int | None
    black_seed: int | None
    board_number: int
    game_index: int
    metadata: dict


def _normalize_seeds(seeds: list[int]) -> list[int]:
    unique = sorted(set(int(seed) for seed in seeds))
    if not unique:
        raise ValueError("At least one participant seed is required")
    return unique


def build_round_robin_rounds(seeds: list[int], games_per_pairing: int = 1) -> list[list[Pairing]]:
    seed_list = _normalize_seeds(seeds)
    if games_per_pairing < 1:
        raise ValueError("games_per_pairing must be >= 1")

    working = list(seed_list)
    has_bye = len(working) % 2 == 1
    if has_bye:
        working.append(None)

    rounds: list[list[Pairing]] = []
    total_rounds = len(working) - 1
    fixed = working[0]
    rotating = working[1:]

    for round_index in range(total_rounds):
        current = [fixed] + rotating
        half = len(current) // 2
        left = current[:half]
        right = list(reversed(current[half:]))

        round_pairings: list[Pairing] = []
        board = 1
        for seed_a, seed_b in zip(left, right):
            if seed_a is None or seed_b is None:
                continue
            for game_idx in range(1, games_per_pairing + 1):
                swap_colors = (round_index + game_idx) % 2 == 1
                white_seed = seed_b if swap_colors else seed_a
                black_seed = seed_a if swap_colors else seed_b
                round_pairings.append(
                    Pairing(
                        white_seed=white_seed,
                        black_seed=black_seed,
                        board_number=board,
                        game_index=game_idx,
                        metadata={"format": "round_robin"},
                    )
                )
            board += 1

        rounds.append(round_pairings)
        rotating = [rotating[-1]] + rotating[:-1]

    return rounds


def build_single_elim_rounds(
    seeds: list[int], games_per_pairing: int = 1, include_third_place: bool = False
) -> list[list[Pairing]]:
    seed_list = _normalize_seeds(seeds)
    if games_per_pairing < 1:
        raise ValueError("games_per_pairing must be >= 1")

    bracket_size = 1
    while bracket_size < len(seed_list):
        bracket_size *= 2
    bracket = seed_list + [None] * (bracket_size - len(seed_list))

    rounds: list[list[Pairing]] = []
    round_number = 1
    current_slots = bracket
    while len(current_slots) > 1:
        next_slots = [None] * (len(current_slots) // 2)
        pairings: list[Pairing] = []
        board = 1
        for idx in range(0, len(current_slots), 2):
            seed_a = current_slots[idx]
            seed_b = current_slots[idx + 1]
            if seed_a is None and seed_b is None:
                board += 1
                continue
            if seed_a is None or seed_b is None:
                next_slots[idx // 2] = seed_b if seed_a is None else seed_a
                board += 1
                continue
            for game_idx in range(1, games_per_pairing + 1):
                swap_colors = game_idx % 2 == 0
                pairings.append(
                    Pairing(
                        white_seed=seed_b if swap_colors else seed_a,
                        black_seed=seed_a if swap_colors else seed_b,
                        board_number=board,
                        game_index=game_idx,
                        metadata={"format": "single_elim", "round": round_number},
                    )
                )
            board += 1
        if pairings:
            rounds.append(pairings)
        current_slots = next_slots
        round_number += 1

    if include_third_place and len(seed_list) >= 4:
        rounds.append(
            [
                Pairing(
                    white_seed=None,
                    black_seed=None,
                    board_number=1,
                    game_index=1,
                    metadata={"format": "single_elim", "round": round_number, "match_type": "third_place_placeholder"},
                )
            ]
        )
    return rounds


def build_swiss_rounds(
    seeds: list[int], rounds_count: int | None = None, games_per_pairing: int = 1
) -> list[list[Pairing]]:
    seed_list = _normalize_seeds(seeds)
    if games_per_pairing < 1:
        raise ValueError("games_per_pairing must be >= 1")
    if rounds_count is None or rounds_count < 1:
        rounds_count = max(1, math.ceil(math.log2(len(seed_list))) + 1)

    standings = {seed: 0.0 for seed in seed_list}
    previous_pairs: set[tuple[int, int]] = set()
    generated_rounds: list[list[Pairing]] = []

    for round_number in range(1, rounds_count + 1):
        ordered = sorted(seed_list, key=lambda s: (-standings[s], s))
        if round_number == 1:
            random.shuffle(ordered)
        used: set[int] = set()
        pairings: list[Pairing] = []
        board = 1

        for seed in ordered:
            if seed in used:
                continue
            opponent = None
            for candidate in ordered:
                if candidate == seed or candidate in used:
                    continue
                pair_key = tuple(sorted((seed, candidate)))
                if pair_key not in previous_pairs:
                    opponent = candidate
                    break
            if opponent is None:
                for candidate in ordered:
                    if candidate != seed and candidate not in used:
                        opponent = candidate
                        break
            if opponent is None:
                standings[seed] += 1.0
                used.add(seed)
                continue

            used.add(seed)
            used.add(opponent)
            pair_key = tuple(sorted((seed, opponent)))
            previous_pairs.add(pair_key)
            for game_idx in range(1, games_per_pairing + 1):
                swap_colors = (round_number + game_idx) % 2 == 0
                white_seed = opponent if swap_colors else seed
                black_seed = seed if swap_colors else opponent
                pairings.append(
                    Pairing(
                        white_seed=white_seed,
                        black_seed=black_seed,
                        board_number=board,
                        game_index=game_idx,
                        metadata={"format": "swiss", "round": round_number},
                    )
                )
            board += 1

        generated_rounds.append(pairings)

    return generated_rounds


def build_double_elim_skeleton(seeds: list[int], games_per_pairing: int = 1) -> list[list[Pairing]]:
    winners_rounds = build_single_elim_rounds(seeds, games_per_pairing=games_per_pairing)
    skeleton: list[list[Pairing]] = []
    for idx, round_pairings in enumerate(winners_rounds, start=1):
        skeleton.append(
            [
                Pairing(
                    white_seed=p.white_seed,
                    black_seed=p.black_seed,
                    board_number=p.board_number,
                    game_index=p.game_index,
                    metadata={**p.metadata, "bracket": "winners", "round": idx},
                )
                for p in round_pairings
            ]
        )
    if skeleton:
        skeleton.append(
            [
                Pairing(
                    white_seed=None,
                    black_seed=None,
                    board_number=1,
                    game_index=1,
                    metadata={"format": "double_elim", "bracket": "grand_final_placeholder"},
                )
            ]
        )
    return skeleton

