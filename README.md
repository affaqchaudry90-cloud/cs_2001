# LEDGER — Digital Bank with Simulated Customers & Fraud Detection

CS 2001 (Introduction to Programming, LUMS, Fall 2026) course project implementing a digital bank core, day-by-day customer simulation, scheduled payments, rollback stack, and rule-based fraud detection using the Python standard library only.

## Authors

- Chaudry Affaq Ur Rehman (`29020161`)
- Ahmed Mohammad Iqbal (`28020022`)

## How to Run

Run the default 60-day simulation (`scenarios/normal.csv`):

```bash
python3 main.py --days 60 --customers 25 --seed 3
```

Run the fraud-heavy scenario (loads all 15 customers by default):

```bash
python3 main.py --scenario scenarios/fraud_heavy.csv
```

Demonstrate `UndoStack` rollback after the run:

```bash
python3 main.py --days 60 --customers 25 --seed 3 --undo 3
```

Test missing-file error handling (prints `Error: ...` with no traceback):

```bash
python3 main.py --scenario missing.csv
```

## Running the Unit Tests

```bash
python3 -m unittest
```

For verbose output:

```bash
python3 -m unittest -v
```

## Command-Line Options

| Option | Default | Description |
|---|---|---|
| `--days` | `60` | Number of banking days to simulate (must be ≥ 1) |
| `--customers` | all rows in CSV | Number of customers to load from the scenario CSV |
| `--seed` | `3` | Seed for deterministic, reproducible simulation runs |
| `--scenario` | `scenarios/normal.csv` | Path to the customer CSV scenario file |
| `--out` | `statements` | Output directory where per-account statements are written |
| `--undo` | `0` | Number of recent applied transactions to roll back after the run |

## Scenario CSV Format

Exact header:

```csv
name,branch,agent,account_kind,opening_rupees,joint_with,opened_days_ago
```

Allowed values:

- `name`: non-empty customer name
- `branch`: `KHI`, `LHR`, or `ISB`
- `agent`: `salaried`, `student`, `merchant`, or `fraudster`
- `account_kind`: `current`, `savings`, `youth`, or `loan`
- `opening_rupees`: non-negative number (rupees)
- `joint_with`: optional name of an earlier customer in the CSV to create a joint account
- `opened_days_ago`: integer from `0` to `365` (triggers recursive back-dated interest on `savings`/`youth` accounts when `> 0`)

## Division of Work

| Owner | Source Modules | Tests & Deliverables |
|---|---|---|
| **Chaudry Affaq Ur Rehman (29020161)** | `ledger/money.py`, `ledger/accounts.py`, `ledger/bank.py`, `ledger/reports.py`, `ledger/files.py` | `tests/test_transactions.py`, `tests/test_queue.py`, `tests/test_fraud.py` |
| **Ahmed Mohammad Iqbal (28020022)** | `ledger/transactions.py`, `ledger/scheduler.py`, `ledger/agents.py`, `ledger/fraud.py` | `tests/test_money.py`, `tests/test_accounts.py`, `tests/test_files.py` |
| **Both Partners** | `ledger/exceptions.py`, `ledger/simulation.py`, `main.py` | `tests/test_transfer_atomicity.py`, `tests/test_simulation.py`, `scenarios/`, `README.md`, `docs/report.pdf`, `docs/uml_diagram.pdf` |

Tests were deliberately cross-written: each partner wrote the tests for the other partner's modules, so every module was checked by someone who did not write it.
