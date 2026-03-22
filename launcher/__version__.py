"""WOPC version string.

importlib.metadata strips leading zeros from PEP 440 versions (e.g.
"2.01.0001" becomes "2.1.1").  This module preserves the exact display
version in N.NN.NNNN format so the GUI shows it correctly.

Updated automatically by ``scripts/release.py``.
"""

VERSION = "2.01.0026"
