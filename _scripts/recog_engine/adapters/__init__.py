"""
ReCog Adapters - Adapter Module

Copyright (c) 2025 Brent Lefebure / EhkoLabs
Licensed under AGPLv3 - See LICENSE in repository root

Adapters connect ReCog to specific applications.
"""

from .base import RecogAdapter
from .memory import MemoryAdapter
from .sqlite import SQLiteAdapter


__all__ = [
    "RecogAdapter",
    "MemoryAdapter",
    "SQLiteAdapter",
]
