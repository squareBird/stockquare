# Backend Code Style

Based on Google Python Style Guide. Enforced by Ruff.

> Reference: https://google.github.io/styleguide/pyguide.html

## Formatter & Linter

- **Ruff** as a single tool for formatting + linting
- Replaces Black, isort, flake8, and pylint

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = [
  "E",   # pycodestyle errors
  "W",   # pycodestyle warnings
  "F",   # pyflakes
  "I",   # isort
  "N",   # pep8-naming
  "UP",  # pyupgrade
  "B",   # flake8-bugbear
  "SIM", # flake8-simplify
  "TCH", # flake8-type-checking
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
```

## Naming

| Target | Convention | Example |
|--------|-----------|---------|
| Module/Package | snake_case | `kis_client.py` |
| Class | PascalCase | `TradingService` |
| Function/Variable | snake_case | `get_balance()`, `access_token` |
| Constant | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Private | leading underscore | `_parse_response()` |

## Type Hints

Type hints are required for all functions. Minimize use of `Any`.

```python
def get_stock_price(symbol: str, market: Market) -> StockPrice:
    ...

async def place_order(order: OrderRequest) -> OrderResponse:
    ...
```

## Docstring

Use Google style docstrings.

```python
def calculate_profit(buy_price: float, sell_price: float, quantity: int) -> float:
    """Calculate profit from buy/sell prices and quantity.

    Args:
        buy_price: Buy price per unit.
        sell_price: Sell price per unit.
        quantity: Number of shares.

    Returns:
        Pre-tax profit amount.

    Raises:
        ValueError: If price or quantity is negative.
    """
```

## Import Order

Automatically sorted by Ruff isort:

1. Standard library (`os`, `datetime`)
2. Third-party (`fastapi`, `httpx`)
3. Local (`app.services`, `app.models`)

```python
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends
from httpx import AsyncClient

from app.models.stock import StockPrice
from app.services.kis import KISClient
```

## General Rules

- Keep functions under 50 lines
- Maximum 3 levels of nesting (use early return)
- Use f-strings (avoid `%` formatting and `.format()`)
- Use `is None` / `is not None` (never `== None`)
