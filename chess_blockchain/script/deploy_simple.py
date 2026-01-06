"""
Simple deployment script for ChessGame contract
Alternative version using direct boa integration
"""

from moccasin.config import get_active_network
import boa


def deploy_chess_game():
    """Deploy the ChessGame contract using boa directly"""
    print("Deploying ChessGame contract...")

    # Get active network
    active_network = get_active_network()
    account = active_network.get_default_account()

    print(f"Network: {active_network.name}")
    print(f"Deploying from: {account.address}")

    # Load and compile the contract
    with open("src/chessgame.vy", "r") as f:
        contract_code = f.read()

    # Deploy with judge address as constructor parameter
    chess_game = boa.loads(contract_code, judge=account.address)

    print(f"\n✅ ChessGame deployed successfully!")
    print(f"Contract address: {chess_game.address}")
    print(f"Judge address: {account.address}")
    print(f"\n📋 Add these to your djangoChess/.env file:")
    print(f"CHESS_CONTRACT_ADDRESS={chess_game.address}")
    print(
        f"JUDGE_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    )

    return chess_game


def moccasin_main():
    """Main function called by moccasin run"""
    return deploy_chess_game()


if __name__ == "__main__":
    deploy_chess_game()
