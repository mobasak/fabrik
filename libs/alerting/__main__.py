"""`python -m alerting` entry point.

A package needs an explicit ``__main__`` module for ``-m`` to work; the
``if __name__ == "__main__"`` block in ``__init__.py`` only fires when the file is
executed directly. Without this, ``python -m alerting --selftest`` dies with
"'alerting' is a package and cannot be directly executed" — and a selftest an
operator cannot invoke is no better than the vacuous checks it was written to avoid.
"""

from . import _main

raise SystemExit(_main())
