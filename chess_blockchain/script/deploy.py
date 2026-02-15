"""
Moccasin deployment script for ChessGame contract
Supports Anvil, Base Sepolia, and Base Mainnet
"""

from moccasin.config import get_active_network
import boa
import sys


def deploy_chess_game():
    """Deploy the ChessGame contract to the active network"""

    # Get active network from Moccasin context
    active_network = get_active_network()
    network_name = active_network.name

    print("=" * 60)
    print(f"🚀 DEPLOYING CHESSGAME CONTRACT")
    print("=" * 60)
    print(f"Network: {network_name}")
    print(
        f"Chain ID: {active_network.chain_id if hasattr(active_network, 'chain_id') else 'N/A'}"
    )

    # Get deployer account
    try:
        account = active_network.get_default_account()
        print(f"Deployer: {account.address}")
    except Exception as e:
        print(f"❌ Error getting account: {e}")
        print("Make sure you have configured your account or set DEPLOYER_PRIVATE_KEY")
        sys.exit(1)

    # Check deployer balance
    if network_name != "pyevm":
        try:
            balance = boa.env.get_balance(account.address)
            balance_eth = balance / 10**18
            print(f"Balance: {balance_eth:.6f} ETH")

            if balance_eth < 0.001:
                print(
                    "⚠️  WARNING: Low balance! You may not have enough ETH for deployment."
                )
                if network_name == "base":
                    print("   You need ~0.01-0.02 ETH for mainnet deployment")
                elif "sepolia" in network_name:
                    print(
                        "   Get test ETH from: https://www.alchemy.com/faucets/base-sepolia"
                    )

                if network_name == "base":  # Production
                    response = input("Continue anyway? (yes/no): ")
                    if response.lower() != "yes":
                        print("Deployment cancelled")
                        sys.exit(1)
        except Exception as e:
            print(f"⚠️  Could not check balance: {e}")

    print("-" * 60)

    # Confirmation for production
    if network_name == "base":
        print("⚠️  YOU ARE DEPLOYING TO BASE MAINNET (PRODUCTION)")
        print("⚠️  THIS WILL COST REAL ETH")
        print(f"⚠️  Judge will be: {account.address}")
        print("-" * 60)
        response = input("Type 'DEPLOY' to confirm: ")
        if response != "DEPLOY":
            print("❌ Deployment cancelled")
            sys.exit(1)

    # Deploy contract with judge address
    print(f"\n📝 Deploying contract with judge: {account.address}")
    print("⏳ This may take a few moments...")

    try:
        # Load and deploy the contract
        chess_game = boa.load("src/chessgame.vy", account.address)

        print("\n" + "=" * 60)
        print("✅ CHESSGAME DEPLOYED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Contract Address: {chess_game.address}")
        print(f"Judge Address: {account.address}")

        # Network-specific next steps
        if network_name == "anvil":
            print("\n📋 NEXT STEPS (Anvil):")
            print(f"1. Update djangoChess/.env.development:")
            print(f"   CHESS_CONTRACT_ADDRESS={chess_game.address}")
            print(
                f"   JUDGE_PRIVATE_KEY=0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
            )
            print(f"\n2. Restart Django server:")
            print(f"   DJANGO_ENV=development python manage.py runserver")

        elif "sepolia" in network_name:
            print("\n📋 NEXT STEPS (Base Sepolia):")
            print(f"1. Update djangoChess/.env.sepolia:")
            print(f"   CHESS_CONTRACT_ADDRESS={chess_game.address}")
            print(f"\n2. View on BaseScan:")
            print(f"   https://sepolia.basescan.org/address/{chess_game.address}")
            print(f"\n3. Test thoroughly before mainnet!")
            print(f"\n4. Start Django with Sepolia config:")
            print(f"   DJANGO_ENV=sepolia python manage.py runserver")

        elif network_name == "base":
            print("\n📋 NEXT STEPS (Base Mainnet - PRODUCTION):")
            print(f"1. Update djangoChess/.env.production:")
            print(f"   CHESS_CONTRACT_ADDRESS={chess_game.address}")
            print(f"\n2. View on BaseScan:")
            print(f"   https://basescan.org/address/{chess_game.address}")
            print(f"\n3. Verify contract (optional but recommended):")
            print(f"   moccasin verify --network base")
            print(f"\n4. Deploy Django to production server")
            print(f"\n5. Test with small amounts first!")

        print("\n⚠️  IMPORTANT:")
        print(f"   - Save this contract address: {chess_game.address}")
        print(f"   - Back up your judge private key securely")
        print(f"   - You cannot change the contract after deployment")
        print("=" * 60)

        return chess_game

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ DEPLOYMENT FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("- Check your account has enough ETH")
        print("- Verify your RPC URL is correct")
        print("- Make sure the network is accessible")

        if "invalid sender" in str(e).lower():
            print("\n⚠️  Invalid sender - check your private key is set correctly")

        sys.exit(1)


def moccasin_main():
    """Main function called by moccasin run"""
    return deploy_chess_game()


if __name__ == "__main__":
    deploy_chess_game()
