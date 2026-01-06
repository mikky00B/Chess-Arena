"""
Run this in Django shell to test signature generation
python manage.py shell < test_signature.py
"""

from main.blockchain_utils import (
    w3,
    chess_contract,
    judge_account,
    generate_winner_signature,
)
from main.models import Game
from django.conf import settings

print("=" * 60)
print("SIGNATURE DEBUGGING")
print("=" * 60)

# Get a completed game
try:
    game = Game.objects.filter(is_active=False, winner__isnull=False).latest("id")
    print(f"\n✓ Found game #{game.id}")
    print(f"  Winner: {game.winner.username}")
    print(f"  Winner address: {game.winner.profile.ethereum_address}")
except Game.DoesNotExist:
    print("\n✗ No completed games found")
    exit()

print("\n" + "=" * 60)
print("CONFIGURATION CHECK")
print("=" * 60)

# Check configuration
print(f"\nContract Address: {settings.CHESS_CONTRACT_ADDRESS}")
print(f"Judge Private Key: {settings.JUDGE_PRIVATE_KEY[:10]}...")
print(f"RPC URL: {settings.BLOCKCHAIN_RPC_URL}")

# Get judge address from contract
try:
    contract_judge = chess_contract.functions.judge_address().call()
    print(f"\nJudge in Contract: {contract_judge}")
    print(f"Judge from .env:    {judge_account.address}")

    if contract_judge.lower() == judge_account.address.lower():
        print("✓ Judge addresses MATCH")
    else:
        print("✗ Judge addresses DO NOT MATCH!")
        print("  This is the problem - contract expects different judge")
except Exception as e:
    print(f"✗ Could not get judge from contract: {e}")

print("\n" + "=" * 60)
print("SIGNATURE GENERATION TEST")
print("=" * 60)

# Generate signature
winner_address = game.winner.profile.ethereum_address
v, r, s = generate_winner_signature(game.id, winner_address)

print(f"\nGenerated signature:")
print(f"  v: {v}")
print(f"  r: {r}")
print(f"  s: {s}")

print("\n" + "=" * 60)
print("RECOMMENDATIONS")
print("=" * 60)

if contract_judge.lower() != judge_account.address.lower():
    print("\n⚠️  PROBLEM FOUND:")
    print("   The contract was deployed with a different judge address")
    print("   than what's in your .env file!")
    print("\n   SOLUTION:")
    print(f"   1. Get the private key for address: {contract_judge}")
    print("   2. Update .env JUDGE_PRIVATE_KEY with that key")
    print("   OR")
    print("   3. Redeploy the contract with current judge account")
else:
    print("\n✓ Configuration looks correct")
    print("  Check Vyper contract signature verification logic")
