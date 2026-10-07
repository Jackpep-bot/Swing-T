"""Operations: pre-flight diagnostics (`swing doctor`) and the unattended nightly pipeline (`swing nightly`).

Nothing here submits an order, and nothing here lets a number from the LLM layer reach one: the nightly
pipeline only calls the same module APIs the CLI commands call (docs/api-contract.md) and writes its
artifacts under `<store dir>/runs/`.
"""
