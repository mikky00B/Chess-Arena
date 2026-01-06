# Chess dApp - Blockchain-Based Chess with Real Stakes

A full-stack decentralized chess platform where players can challenge each other with real cryptocurrency at stake. Built with Django, Vyper smart contracts, and real-time WebSocket gameplay.

## 🎯 Features

- **Real-time multiplayer chess** using Django Channels and WebSockets
- **Blockchain escrow system** with Vyper smart contracts
- **ELO rating system** for competitive play
- **Server-side time control** to prevent cheating
- **Judge-signed payouts** for secure fund distribution
- **Draw handling** with automatic refunds
- **Abandonment protection** with timeout claims

## 🏗️ Architecture

### Frontend
- **Django Templates** with Tailwind CSS
- **Alpine.js** for reactive UI components
- **Chessboard.js** for chess piece visualization
- **HTMX** for dynamic lobby updates

### Backend
- **Django** for web framework
- **Django Channels** for WebSocket connections
- **Python-chess** for move validation and game logic
- **PostgreSQL** for data persistence
- **Redis** for channel layer

### Blockchain
- **Vyper smart contracts** for escrow logic
- **Web3.py** for blockchain interaction
- **EIP-191 compliant signatures** for security
- **Judge oracle pattern** for off-chain computation verification

## 🔒 Security Features

### Fixed Vulnerabilities

1. **Server-Side Time Management**
   - All time calculations happen on the server
   - Client only displays server-provided times
   - Prevents client-side manipulation

2. **EIP-191 Compliant Signatures**
   - Proper Ethereum signed message format
   - Protection against signature malleability
   - Replay attack prevention with nonce tracking

3. **Draw Handling**
   - Dedicated smart contract function for draws
   - Automatic refunds to both players
   - Judge-signed draw verification

4. **Timeout Protection**
   - Players can claim abandoned games after 24 hours
   - Prevents fund lockup from disconnected opponents
   - Automatic forfeit on timer expiration

## 📁 Project Structure

```
chess-dapp/
├── models.py              # Database models (Game, Profile, Move)
├── views.py               # Django views
├── consumers.py           # WebSocket consumer (FIXED: server-side time)
├── chess_logic.py         # Chess move validation
├── blockchain_views.py    # API endpoints for blockchain interaction (NEW)
├── blockchain_utils.py    # Web3 utilities and signature generation (NEW)
├── signals.py             # ELO updates and signature generation (FIXED)
├── chessgame.vy          # Smart contract (FIXED: EIP-191, draws, timeout)
├── routing.py            # WebSocket URL routing
├── templates/
│   └── main/
│       ├── lobby.html    # Game lobby
│       └── board2.html   # Game interface (FIXED: timer sync)
└── requirements.txt      # Python dependencies
```

## 🚀 Getting Started

### 1. Clone and Install

```bash
git clone <your-repo>
cd chess-dapp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Deploy Smart Contract

```bash
# Compile contract
vyper chessgame.vy -f abi > chessgame_abi.json
vyper chessgame.vy -f bytecode > chessgame_bytecode.txt

# Deploy (use provided script or manually)
python deploy_contract.py
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 5. Start Services

```bash
# Terminal 1: Redis
redis-server

# Terminal 2: Django
python manage.py runserver
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production setup.

## 🎮 How It Works

### Game Flow

1. **Create Challenge**: Player 1 creates a game and deposits ETH
2. **Join Game**: Player 2 joins and matches the bet
3. **Play**: Real-time chess with WebSocket updates
4. **Outcome**: Server determines winner/draw
5. **Signature**: Django generates judge-signed payout authorization
6. **Claim**: Winner calls smart contract with signature to claim funds

### Smart Contract Functions

- `deposit(game_id)`: Create or join a challenge with ETH
- `claim_winnings(game_id, winner, v, r, s)`: Claim pot with judge signature
- `settle_draw(game_id, v, r, s)`: Refund both players on draw
- `claim_abandonment(game_id)`: Claim pot if opponent times out

### API Endpoints

- `POST /api/verify-deposit/<game_id>/`: Verify deposit transaction
- `GET /api/get-signature/<game_id>/`: Get signature for claiming
- `POST /api/mark-payout/<game_id>/`: Mark payout as claimed
- `GET /api/challenge-info/<game_id>/`: Get on-chain challenge state
- `POST /api/update-address/`: Update user's Ethereum address
- `GET /api/estimate-gas/<game_id>/`: Estimate claim gas cost

## 🧪 Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=main --cov-report=html
```

## 🐛 Known Limitations

1. **Chess Engine Detection**: No automated anti-cheat system
   - Recommendation: Keep stakes low ($1-5) to discourage cheating
   - Future: Implement statistical move analysis

2. **Gas Costs**: Winner pays gas to claim (typically $2-10 on mainnet)
   - Recommendation: Use L2 solutions (Arbitrum, Optimism) for lower fees

3. **Centralization**: Judge server must sign all payouts
   - Trade-off: Allows off-chain chess computation while maintaining security

## 📊 Gas Estimates (Sepolia)

- Deploy Contract: ~1,500,000 gas
- Deposit: ~80,000 gas
- Claim Winnings: ~60,000 gas
- Settle Draw: ~100,000 gas

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Smart Contracts | Vyper 0.4.0 |
| Backend | Django 4.2 |
| Database | PostgreSQL |
| Cache/Channels | Redis |
| WebSockets | Django Channels |
| Blockchain | Web3.py, eth-account |
| Frontend | Tailwind CSS, Alpine.js |
| Chess Logic | python-chess |

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## ⚠️ Disclaimer

This is educational/portfolio software. Use at your own risk. Always test thoroughly on testnets before deploying to mainnet. Never bet more than you can afford to lose.

## 📧 Contact

Your Name - [@Clever00__](https://twitter.com/Clever00__)

Project Link: [https://github.com/yourusername/chess-Arena](https://github.com/yourusername/chess-Arena)