"""
Moccasin deployment script for ChessGame contract
"""

from moccasin.config import get_active_network
import boa


def deploy_chess_game():
    """Deploy the ChessGame contract"""
    print("Deploying ChessGame contract...")

    # Get active network and account from Moccasin context
    active_network = get_active_network()
    account = active_network.get_default_account()

    print(f"Network: {active_network.name}")
    print(f"Deploying from: {account.address}")

    # Load the contract from file
    chess_game = boa.load("src/chessgame.vy", account.address)

    print(f"\n✅ ChessGame deployed successfully!")
    print(f"Contract address: {chess_game.address}")
    print(f"Judge address: {account.address}")
    print(f"\n📋 Add these to your djangoChess/.env file:")
    print(f"CHESS_CONTRACT_ADDRESS={chess_game.address}")
    print(f"BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545")

    # For Anvil default account (account 0)
    print(
        f"JUDGE_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    )
    print(f"\n⚠️  IMPORTANT: Only use this private key for local testing!")

    return chess_game


def moccasin_main():
    """Main function called by moccasin run"""
    return deploy_chess_game()


if __name__ == "__main__":
    deploy_chess_game()
