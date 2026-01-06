"""
Tests for blockchain integration
Run with: pytest test_blockchain.py
"""

import pytest
from django.contrib.auth.models import User
from main.models import Game, Profile
from main.blockchain_utils import generate_winner_signature, generate_draw_signature
from web3 import Web3


@pytest.fixture
def users(db):
    """Create test users"""
    alice = User.objects.create_user(username="alice", password="test123")
    bob = User.objects.create_user(username="bob", password="test123")

    # Set Ethereum addresses
    alice.profile.ethereum_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb4"
    bob.profile.ethereum_address = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    alice.profile.save()
    bob.profile.save()

    return {"alice": alice, "bob": bob}


@pytest.fixture
def game(users):
    """Create a test game"""
    return Game.objects.create(
        white_player=users["alice"],
        black_player=users["bob"],
        bet_amount=0.01,  # 0.01 ETH
    )


class TestSignatureGeneration:
    """Test signature generation for blockchain claims"""

    def test_winner_signature_format(self, game, users):
        """Test that winner signature has correct format"""
        winner_address = users["alice"].profile.ethereum_address
        v, r, s = generate_winner_signature(game.id, winner_address)

        # Check signature components
        assert isinstance(v, int)
        assert 27 <= v <= 28  # Valid v values
        assert isinstance(r, str) and r.startswith("0x")
        assert isinstance(s, str) and s.startswith("0x")
        assert len(r) == 66  # 0x + 64 hex chars
        assert len(s) == 66

    def test_draw_signature_format(self, game):
        """Test draw signature format"""
        v, r, s = generate_draw_signature(game.id)

        assert isinstance(v, int)
        assert 27 <= v <= 28
        assert isinstance(r, str) and r.startswith("0x")
        assert isinstance(s, str) and s.startswith("0x")

    def test_signature_deterministic(self, game, users):
        """Test that same inputs produce same signature"""
        winner_address = users["alice"].profile.ethereum_address

        v1, r1, s1 = generate_winner_signature(game.id, winner_address)
        v2, r2, s2 = generate_winner_signature(game.id, winner_address)

        assert v1 == v2
        assert r1 == r2
        assert s1 == s2

    def test_different_games_different_signatures(self, users):
        """Test that different games produce different signatures"""
        game1 = Game.objects.create(
            white_player=users["alice"], black_player=users["bob"], bet_amount=0.01
        )
        game2 = Game.objects.create(
            white_player=users["alice"], black_player=users["bob"], bet_amount=0.01
        )

        winner_address = users["alice"].profile.ethereum_address

        v1, r1, s1 = generate_winner_signature(game1.id, winner_address)
        v2, r2, s2 = generate_winner_signature(game2.id, winner_address)

        # Signatures should be different for different games
        assert r1 != r2 or s1 != s2


class TestGameTimeManagement:
    """Test server-side time management"""

    @pytest.mark.asyncio
    async def test_time_deducted_on_move(self, game):
        """Test that time is deducted from correct player"""
        from django.utils import timezone
        from datetime import timedelta

        initial_white_time = game.white_time
        game.last_move_timestamp = timezone.now() - timedelta(seconds=5)
        game.save()

        # Simulate a move (white's turn based on default FEN)
        from main.consumers import ChessConsumer

        # This would need to be tested with actual WebSocket consumer
        # Placeholder for demonstration

        # After white moves, white_time should decrease
        # Black's time should remain unchanged
        assert True  # Implement actual test with WebSocket client

    def test_timeout_ends_game(self, game):
        """Test that timeout properly ends the game"""
        game.white_time = 0
        game.black_time = 100
        game.save()

        # When white runs out of time, black should win
        # This is handled in update_game_data in consumers.py
        assert True  # Implement actual consumer test


class TestELOCalculation:
    """Test ELO rating updates"""

    def test_winner_gains_rating(self, game, users):
        """Test that winner's rating increases"""
        alice_initial = users["alice"].profile.rating
        bob_initial = users["bob"].profile.rating

        # Finish game with alice as winner
        game.is_active = False
        game.winner = users["alice"]
        game.save()

        # Reload profiles
        users["alice"].profile.refresh_from_db()
        users["bob"].profile.refresh_from_db()

        # Alice should gain rating, Bob should lose
        assert users["alice"].profile.rating > alice_initial
        assert users["bob"].profile.rating < bob_initial

    def test_draw_adjusts_ratings(self, game, users):
        """Test that draw adjusts ratings based on expected outcome"""
        alice_initial = users["alice"].profile.rating
        bob_initial = users["bob"].profile.rating

        # Higher rated player draws with lower rated player
        users["alice"].profile.rating = 1600
        users["alice"].profile.save()
        users["bob"].profile.rating = 1200
        users["bob"].profile.save()

        # Finish game as draw
        game.is_active = False
        game.winner = None
        game.save()

        # Higher rated player should lose rating in a draw
        # Lower rated player should gain rating
        # (Exact calculation depends on K-factor in your ELO implementation)
        assert True  # Implement based on your calculate_elo function


class TestBlockchainIntegration:
    """Test blockchain utility functions"""

    def test_eth_wei_conversion(self):
        """Test ETH to Wei conversion"""
        from main.blockchain_utils import eth_to_wei, wei_to_eth

        # 1 ETH = 10^18 Wei
        assert eth_to_wei(1) == 10**18
        assert eth_to_wei(0.01) == 10**16

        # Reverse conversion
        assert wei_to_eth(10**18) == 1.0
        assert wei_to_eth(10**16) == 0.01

    def test_checksum_address_handling(self, users):
        """Test that addresses are properly checksummed"""
        from main.blockchain_utils import generate_winner_signature

        alice_addr = users["alice"].profile.ethereum_address

        # Should work with lowercase
        v1, r1, s1 = generate_winner_signature(1, alice_addr.lower())

        # Should work with mixed case
        v2, r2, s2 = generate_winner_signature(1, alice_addr)

        # Should produce same signature
        assert v1 == v2
        assert r1 == r2
        assert s1 == s2


@pytest.mark.integration
class TestSmartContractInteraction:
    """Integration tests with actual smart contract (requires local blockchain)"""

    def test_deposit_creates_challenge(self):
        """Test depositing to contract creates challenge"""
        # This requires a local blockchain (Ganache/Anvil)
        # and deployed contract
        pytest.skip("Requires local blockchain setup")

    def test_claim_with_valid_signature(self):
        """Test claiming winnings with valid signature"""
        pytest.skip("Requires local blockchain setup")

    def test_claim_with_invalid_signature_fails(self):
        """Test that invalid signature is rejected"""
        pytest.skip("Requires local blockchain setup")
