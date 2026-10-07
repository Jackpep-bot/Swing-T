"""Data layer: DuckDB store, NYSE calendar, universe screen, ingest, bar providers (sample, massive, eodhd,
alpaca; registered as ``bar_provider``), and reference/alt-data clients (edgar, alphavantage, quiver, altdata).
Modules are imported by ``core.registry.discover``; heavy vendor SDKs are imported lazily inside functions."""
