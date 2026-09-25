"""Shared test bootstrap: put backend/ and Flood_prediction/ on sys.path."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(_HERE))  # backend/
FLOOD = os.path.join(BACKEND, "Flood_prediction")
for p in (BACKEND, FLOOD):
    if p not in sys.path:
        sys.path.insert(0, p)
