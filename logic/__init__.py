"""Logic layer.

- logic/atoms/ — Core atoms: generic, reusable pure functions (JSON-in, JSON-out).
  No domain knowledge. Don't know which column, which file, or which business context.

- Business logic lives in pipeline.py + runners/ops.py — it decides WHICH atom to call,
  on WHICH data, with WHICH parameters. Each business pipeline has its own folder lifecycle.
"""
