"""OSINT data source adapters."""

from ignifer.adapters.acled import ACLEDAdapter
from ignifer.adapters.aisstream import AISStreamAdapter
from ignifer.adapters.base import (
    AdapterAuthError,
    AdapterError,
    AdapterParseError,
    AdapterTimeoutError,
    OSINTAdapter,
    handle_http_status,
)
from ignifer.adapters.gdelt import GDELTAdapter
from ignifer.adapters.opensky import OpenSkyAdapter
from ignifer.adapters.opensanctions import OpenSanctionsAdapter
from ignifer.adapters.wikidata import WikidataAdapter
from ignifer.adapters.worldbank import WorldBankAdapter

__all__ = [
    "OSINTAdapter",
    "AdapterError",
    "AdapterTimeoutError",
    "AdapterParseError",
    "AdapterAuthError",
    "ACLEDAdapter",
    "AISStreamAdapter",
    "GDELTAdapter",
    "OpenSanctionsAdapter",
    "OpenSkyAdapter",
    "WikidataAdapter",
    "WorldBankAdapter",
    "handle_http_status",
]
