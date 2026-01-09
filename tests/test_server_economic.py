"""Tests for economic_context tool in server.py."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ignifer.adapters.base import AdapterError, AdapterTimeoutError
from ignifer.models import OSINTResult, ResultStatus
from ignifer.server import economic_context


# Helper to call the wrapped function
async def call_economic_context(country: str) -> str:
    """Call the economic_context tool function."""
    return await economic_context.fn(country)


@pytest.fixture
def worldbank_response():
    """Load the World Bank fixture response."""
    fixture_path = Path(__file__).parent / "fixtures" / "worldbank_response.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def mock_osint_result():
    """Create a mock OSINTResult for testing."""
    def _make_result(
        indicator: str,
        value: float | None = None,
        year: str = "2023",
        country: str = "United States"
    ):
        retrieved_at = datetime.now(timezone.utc)
        if value is None:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=f"{indicator} {country}",
                results=[],
                sources=[],
                retrieved_at=retrieved_at,
            )
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=f"{indicator} {country}",
            results=[{
                "indicator": indicator,
                "country": country,
                "year": year,
                "value": value,
            }],
            sources=[],
            retrieved_at=retrieved_at,
        )
    return _make_result


def create_no_data_result():
    """Create a NO_DATA result."""
    return OSINTResult(
        status=ResultStatus.NO_DATA,
        query="test",
        results=[],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )


# Number of indicators: 3 core + 4 E1 + 4 E2 + 4 E4 = 15
INDICATOR_COUNT = 15


@pytest.fixture
def mock_all_adapters():
    """Context manager that mocks WorldBank, GDELT, and Wikidata adapters."""
    with patch("ignifer.server._get_worldbank") as mock_wb, \
         patch("ignifer.server._get_adapter") as mock_gdelt, \
         patch("ignifer.server._get_wikidata") as mock_wiki:

        # GDELT mock - return empty results (silent degradation)
        gdelt_adapter = AsyncMock()
        gdelt_adapter.query.return_value = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )
        mock_gdelt.return_value = gdelt_adapter

        # Wikidata mock - return empty results (silent degradation)
        wiki_adapter = AsyncMock()
        wiki_adapter.query.return_value = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )
        wiki_adapter.lookup_by_qid.return_value = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )
        mock_wiki.return_value = wiki_adapter

        # WorldBank mock - will be configured per test
        wb_adapter = AsyncMock()
        mock_wb.return_value = wb_adapter

        yield {
            "worldbank": wb_adapter,
            "gdelt": gdelt_adapter,
            "wikidata": wiki_adapter,
        }


@pytest.mark.asyncio
async def test_economic_context_success(mock_osint_result, mock_all_adapters):
    """Test successful economic context retrieval."""
    wb = mock_all_adapters["worldbank"]

    # Mock responses for all 15 indicators
    wb.query.side_effect = [
        # Core indicators (3)
        mock_osint_result("GDP (current US$)", 25462700000000),  # $25.46 trillion
        mock_osint_result("GDP per capita (current US$)", 76330),
        mock_osint_result("Population, total", 334900000),  # 334.9 million
        # E1 Vulnerability (4)
        mock_osint_result("External debt", 50.0),
        mock_osint_result("Current account", -3.5),
        mock_osint_result("Total reserves", 2.1),
        mock_osint_result("Short-term debt", 25.0),
        # E2 Trade (4)
        mock_osint_result("Exports", 11.5),
        mock_osint_result("Imports", 14.2),
        mock_osint_result("Trade openness", 25.7),
        mock_osint_result("Trade balance", -948100000000),  # -$948.1B
        # E4 Financial (4)
        mock_osint_result("Inflation", 4.1),
        mock_osint_result("Unemployment", 3.6),
        mock_osint_result("FDI inflows", 1.5),
        mock_osint_result("Domestic credit", 220.0),
    ]

    result = await call_economic_context("United States")

    # Verify call count
    assert wb.query.call_count == INDICATOR_COUNT

    # Check output format
    assert "ECONOMIC CONTEXT" in result
    assert "COUNTRY: United States" in result
    assert "KEY INDICATORS (2023):" in result
    assert "$25.46 trillion" in result
    assert "$76,330" in result
    assert "334.9 million" in result

    # E1 section
    assert "VULNERABILITY ASSESSMENT (E1):" in result
    assert "50.0% of GNI" in result
    assert "-3.5% of GDP" in result

    # E2 section
    assert "TRADE PROFILE (E2):" in result
    assert "11.5% of GDP" in result  # Exports
    assert "-$948.1 billion" in result

    # E4 section
    assert "FINANCIAL INDICATORS (E4):" in result
    assert "4.1%" in result  # Inflation
    assert "3.6%" in result  # Unemployment

    assert "Sources: World Bank Open Data" in result
    assert "Retrieved:" in result


@pytest.mark.asyncio
async def test_economic_context_partial_data(mock_osint_result, mock_all_adapters):
    """Test economic context with partial data availability."""
    wb = mock_all_adapters["worldbank"]

    # Some indicators return data, some don't
    wb.query.side_effect = [
        # Core indicators
        mock_osint_result("GDP (current US$)", 25462700000000),
        mock_osint_result("GDP per capita (current US$)", None),  # No data
        mock_osint_result("Population, total", 334900000),
        # E1 - all no data
        create_no_data_result(),
        create_no_data_result(),
        create_no_data_result(),
        create_no_data_result(),
        # E2 - partial
        mock_osint_result("Exports", 11.5),
        create_no_data_result(),
        create_no_data_result(),
        mock_osint_result("Trade balance", -948100000000),
        # E4
        mock_osint_result("Inflation", 4.1),
        create_no_data_result(),
        create_no_data_result(),
        create_no_data_result(),
    ]

    result = await call_economic_context("United States")

    # Should still return formatted output
    assert "ECONOMIC CONTEXT" in result
    assert "COUNTRY: United States" in result
    assert "$25.46 trillion" in result  # GDP present
    assert "$76,330" not in result  # GDP per capita missing

    # E1 section should be absent since all NO_DATA
    assert "VULNERABILITY ASSESSMENT (E1):" not in result

    # E2 section should be present with partial data
    assert "TRADE PROFILE (E2):" in result
    assert "11.5% of GDP" in result

    # E4 section present with inflation
    assert "FINANCIAL INDICATORS (E4):" in result
    assert "4.1%" in result


@pytest.mark.asyncio
async def test_economic_context_country_not_found(mock_all_adapters):
    """Test economic context with invalid country."""
    wb = mock_all_adapters["worldbank"]

    # All queries return NO_DATA
    wb.query.return_value = create_no_data_result()

    result = await call_economic_context("InvalidCountry")

    assert "Country Not Found" in result
    assert "InvalidCountry" in result
    assert "Check the spelling" in result
    assert "ISO country code" in result


@pytest.mark.asyncio
async def test_economic_context_timeout(mock_all_adapters):
    """Test economic context with timeout error."""
    wb = mock_all_adapters["worldbank"]
    wb.query.side_effect = AdapterTimeoutError("worldbank", 15.0)

    result = await call_economic_context("Germany")

    assert "Request Timed Out" in result
    assert "Germany" in result
    assert "Try again in a moment" in result
    assert "network connection" in result


@pytest.mark.asyncio
async def test_economic_context_rate_limited(mock_all_adapters):
    """Test economic context with rate limit error (via AdapterError)."""
    wb = mock_all_adapters["worldbank"]
    error = AdapterError("worldbank", "Rate limit exceeded")
    wb.query.side_effect = error

    result = await call_economic_context("Japan")

    assert "Service Temporarily Unavailable" in result
    assert "rate limiting" in result
    assert "Wait a few minutes" in result


@pytest.mark.asyncio
async def test_economic_context_rate_limited_status(mock_all_adapters):
    """Test economic context with RATE_LIMITED result status."""
    wb = mock_all_adapters["worldbank"]

    # Return RATE_LIMITED status from adapter
    rate_limited_result = OSINTResult(
        status=ResultStatus.RATE_LIMITED,
        query="gdp China",
        results=[],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )
    wb.query.return_value = rate_limited_result

    result = await call_economic_context("China")

    assert "Service Temporarily Unavailable" in result
    assert "rate limiting" in result
    assert "Try again in a few minutes" in result


@pytest.mark.asyncio
async def test_economic_context_adapter_error(mock_all_adapters):
    """Test economic context with general adapter error."""
    wb = mock_all_adapters["worldbank"]
    error = AdapterError("worldbank", "Unknown error occurred")
    wb.query.side_effect = error

    result = await call_economic_context("France")

    assert "Unable to Retrieve Data" in result
    assert "France" in result
    assert "Unknown error occurred" in result


@pytest.mark.asyncio
async def test_economic_context_unexpected_error(mock_all_adapters):
    """Test economic context with unexpected exception."""
    wb = mock_all_adapters["worldbank"]
    wb.query.side_effect = ValueError("Unexpected error")

    result = await call_economic_context("India")

    assert "Error" in result
    assert "unexpected error" in result
    assert "India" in result


@pytest.mark.asyncio
async def test_economic_context_different_years(mock_all_adapters):
    """Test economic context when indicators have different years."""
    wb = mock_all_adapters["worldbank"]

    def make_year_result(indicator: str, value: float, year: str):
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=f"{indicator} Brazil",
            results=[{
                "indicator": indicator,
                "country": "Brazil",
                "year": year,
                "value": value,
            }],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

    # Different years for different indicators - first one determines displayed year
    wb.query.side_effect = [
        make_year_result("GDP (current US$)", 2000000000000, "2023"),
        make_year_result("GDP per capita", 10000, "2023"),
        make_year_result("Population", 215000000, "2023"),
    ] + [create_no_data_result()] * (INDICATOR_COUNT - 3)

    result = await call_economic_context("Brazil")

    # Should use the year from the first indicator
    assert "KEY INDICATORS (2023):" in result
    assert "Brazil" in result


@pytest.mark.asyncio
async def test_economic_context_positive_trade_balance(mock_osint_result, mock_all_adapters):
    """Test formatting of positive trade balance."""
    wb = mock_all_adapters["worldbank"]

    # Create results with positive trade balance
    wb.query.side_effect = [
        mock_osint_result("GDP", 1500000000000),
        mock_osint_result("GDP per capita", 50000),
        mock_osint_result("Population", 50000000),
    ] + [create_no_data_result()] * 4 + [  # E1 no data
        create_no_data_result(),  # Exports
        create_no_data_result(),  # Imports
        create_no_data_result(),  # Trade openness
        mock_osint_result("Trade balance", 100000000000),  # +$100B
    ] + [create_no_data_result()] * 4  # E4 no data

    result = await call_economic_context("TestCountry")

    # Check for positive sign
    assert "+$100.0 billion" in result


@pytest.mark.asyncio
async def test_economic_context_country_alias(mock_all_adapters):
    """Test that country aliases work correctly."""
    wb = mock_all_adapters["worldbank"]

    # Mock successful response for GDP, NO_DATA for others
    success_result = OSINTResult(
        status=ResultStatus.SUCCESS,
        query="gdp USA",
        results=[{
            "indicator": "GDP (current US$)",
            "country": "United States",
            "year": "2023",
            "value": 25000000000000,
        }],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

    wb.query.side_effect = [success_result] + [create_no_data_result()] * (INDICATOR_COUNT - 1)

    # Use "USA" alias instead of "United States"
    result = await call_economic_context("USA")

    # Should resolve to United States
    assert "United States" in result
    assert "ECONOMIC CONTEXT" in result


@pytest.mark.asyncio
async def test_economic_context_regional_aggregate_eu(mock_all_adapters):
    """Test economic context for European Union regional aggregate."""
    wb = mock_all_adapters["worldbank"]

    success_result = OSINTResult(
        status=ResultStatus.SUCCESS,
        query="gdp European Union",
        results=[{
            "indicator": "GDP (current US$)",
            "country": "European Union",
            "year": "2023",
            "value": 16640000000000,  # ~$16.64 trillion
        }],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

    wb.query.side_effect = [success_result] + [create_no_data_result()] * (INDICATOR_COUNT - 1)

    result = await call_economic_context("European Union")

    assert "ECONOMIC CONTEXT" in result
    assert "European Union" in result
    assert "$16.64 trillion" in result


@pytest.mark.asyncio
async def test_economic_context_regional_aggregate_sub_saharan_africa(mock_all_adapters):
    """Test economic context for Sub-Saharan Africa regional aggregate."""
    wb = mock_all_adapters["worldbank"]

    success_result = OSINTResult(
        status=ResultStatus.SUCCESS,
        query="gdp Sub-Saharan Africa",
        results=[{
            "indicator": "GDP (current US$)",
            "country": "Sub-Saharan Africa",
            "year": "2022",
            "value": 1860000000000,  # ~$1.86 trillion
        }],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

    wb.query.side_effect = [success_result] + [create_no_data_result()] * (INDICATOR_COUNT - 1)

    result = await call_economic_context("Sub-Saharan Africa")

    assert "ECONOMIC CONTEXT" in result
    assert "Sub-Saharan Africa" in result
    assert "$1.86 trillion" in result


@pytest.mark.asyncio
async def test_economic_context_with_wikidata_context(mock_osint_result, mock_all_adapters):
    """Test economic context includes Wikidata government context when available."""
    wb = mock_all_adapters["worldbank"]
    wiki = mock_all_adapters["wikidata"]

    # Mock WorldBank responses
    wb.query.side_effect = [
        mock_osint_result("GDP", 4000000000000, country="Germany"),
    ] + [create_no_data_result()] * (INDICATOR_COUNT - 1)

    # Mock Wikidata search response (returns Q-ID)
    wiki.query.return_value = OSINTResult(
        status=ResultStatus.SUCCESS,
        query="Germany",
        results=[{
            "qid": "Q183",
            "label": "Germany",
            "description": "country in Central Europe",
        }],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

    # Mock Wikidata lookup_by_qid response (returns full properties)
    wiki.lookup_by_qid.return_value = OSINTResult(
        status=ResultStatus.SUCCESS,
        query="Q183",
        results=[{
            "qid": "Q183",
            "label": "Germany",
            "description": "country in Central Europe",
            "head_of_government": "Olaf Scholz",
            "currency": "Euro",
        }],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

    result = await call_economic_context("Germany")

    assert "ECONOMIC CONTEXT" in result
    assert "Germany" in result
    assert "Olaf Scholz" in result
    assert "Currency: Euro" in result
    assert "Wikidata" in result  # Source attribution


@pytest.mark.asyncio
async def test_economic_context_with_gdelt_events(mock_osint_result, mock_all_adapters):
    """Test economic context includes GDELT events when available."""
    wb = mock_all_adapters["worldbank"]
    gdelt = mock_all_adapters["gdelt"]

    # Mock WorldBank responses
    wb.query.side_effect = [
        mock_osint_result("GDP", 4000000000000, country="Germany"),
    ] + [create_no_data_result()] * (INDICATOR_COUNT - 1)

    # Mock GDELT response with economic events
    gdelt.query.return_value = OSINTResult(
        status=ResultStatus.SUCCESS,
        query="Germany economy",
        results=[
            {"title": "Germany trade deal announced", "seendate": "2026-01-08T12:00:00Z"},
            {"title": "ECB holds interest rates", "seendate": "2026-01-07T10:00:00Z"},
        ],
        sources=[],
        retrieved_at=datetime.now(timezone.utc),
    )

    result = await call_economic_context("Germany")

    assert "ECONOMIC CONTEXT" in result
    assert "RECENT ECONOMIC EVENTS:" in result
    assert "Germany trade deal announced" in result
    assert "ECB holds interest rates" in result
    assert "GDELT" in result  # Source attribution


@pytest.mark.asyncio
async def test_economic_context_silent_degradation(mock_osint_result, mock_all_adapters):
    """Test that GDELT/Wikidata failures degrade silently."""
    wb = mock_all_adapters["worldbank"]
    gdelt = mock_all_adapters["gdelt"]
    wiki = mock_all_adapters["wikidata"]

    # Mock WorldBank responses - success
    wb.query.side_effect = [
        mock_osint_result("GDP", 4000000000000, country="Germany"),
    ] + [create_no_data_result()] * (INDICATOR_COUNT - 1)

    # GDELT throws exception
    gdelt.query.side_effect = Exception("GDELT is down")

    # Wikidata throws exception
    wiki.query.side_effect = Exception("Wikidata is down")

    result = await call_economic_context("Germany")

    # Should still return valid output with World Bank data
    assert "ECONOMIC CONTEXT" in result
    assert "Germany" in result
    assert "$4.00 trillion" in result

    # Should NOT contain error messages
    assert "Error" not in result
    assert "GDELT is down" not in result
    assert "Wikidata is down" not in result

    # Should only show World Bank as source
    assert "Sources: World Bank Open Data" in result
    assert "GDELT" not in result
    assert "Wikidata" not in result
