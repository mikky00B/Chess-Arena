# Contracts

V2 contracts live here.

The first contract is `src/challenge_escrow_v2.vy`, a native-token challenge
escrow with:

- expected-player deposits
- wrong-player, wrong-amount, and duplicate-deposit rejection
- authority-only winner settlement
- authority-only draw refunds
- replay protection
- expired unfunded refunds
- no arbitrary abandonment pot claim

Run contract checks from this directory:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m vyper src\challenge_escrow_v2.vy
```
