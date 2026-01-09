"""OSINT data source adapters."""

from ignifer.adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterParseError,
    AdapterTimeoutError,
    OSINTAdapter,
)
from ignifer.adapters.gdelt import GDELTAdapter
from ignifer.adapters.wikidata import WikidataAdapter
from ignifer.adapters.worldbank import WorldBankAdapter

__all__ = [
    "OSINTAdapter",
    "AdapterError",
    "AdapterTimeoutError",
    "AdapterParseError",
    "AdapterAuthError",
    "GDELTAdapter",
    "WikidataAdapter",
    "WorldBankAdapter",
]
