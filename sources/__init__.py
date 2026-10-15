# sources/__init__.py
"""
Job source adapters.

To add a new source:
1. Create a new module in this directory.
2. Implement a class that inherits from BaseSource.
3. Register it in ALL_SOURCES below.
"""

from sources.remotive import RemotiveSource
from sources.arbeitnow import ArbeitnowSource
from sources.greenhouse import GreenhouseSource
from sources.lever import LeverSource

ALL_SOURCES = [
    RemotiveSource,
    ArbeitnowSource,
    GreenhouseSource,
    LeverSource,
]
