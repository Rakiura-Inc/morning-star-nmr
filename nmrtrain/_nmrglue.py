"""nmrglue, imported once with its warnings silenced (it warns about every Bruker file it reads)."""

import warnings

warnings.filterwarnings("ignore", module="nmrglue")

import nmrglue as ng  # noqa: E402 (the filter above must be in place before nmrglue loads)

__all__ = ["ng"]
