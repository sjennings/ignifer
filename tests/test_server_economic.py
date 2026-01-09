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
    def _make_result(indicator: str, value: float | None = None, year: str = "2023"):
        retrieved_at = datetime.now(timezone.utc)
        if value is None:
            return OSINTResult(
                status=ResultStatus.NO_DATA,
                query=f"{indicator} United States",
                results=[],
                sources=[],
                retrieved_at=retrieved_at,
            )
        return OSINTResult(
            status=ResultStatus.SUCCESS,
            query=f"{indicator} United States",
            results=[{
                "indicator": indicator,
                "country": "United States",
                "year": year,
                "value": value,
            }],
            sources=[],
            retrieved_at=retrieved_at,
        )
    return _make_result


@pytest.mark.asyncio
async def test_economic_context_success(mock_osint_result):
    """Test successful economic context retrieval."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Mock responses for each indicator
        mock_adapter.query.side_effect = [
            mock_osint_result("GDP (current US$)", 25462700000000),  # $25.46 trillion
            mock_osint_result("GDP per capita (current US$)", 76330),
            mock_osint_result("Inflation, consumer prices (annual %)", 4.1),
            mock_osint_result("Unemployment, total (% of total labor force)", 3.6),
            # Trade balance: -$948.1B
            mock_osint_result(
                "External balance on goods and services (current US$)", -948100000000
            ),
            mock_osint_result("Population, total", 334900000),  # 334.9 million
        ]

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("United States")

        # Verify call count
        assert mock_adapter.query.call_count == 6

        # Check output format
        assert "ECONOMIC CONTEXT" in result
        assert "COUNTRY: United States" in result
        assert "KEY INDICATORS (2023):" in result
        assert "$25.46 trillion" in result
        assert "$76,330" in result
        assert "4.1%" in result
        assert "3.6%" in result
        assert "-$948.1 billion" in result
        assert "334.9 million" in result
        assert "Source: World Bank Open Data" in result
        assert "Retrieved:" in result


@pytest.mark.asyncio
async def test_economic_context_partial_data(mock_osint_result):
    """Test economic context with partial data availability."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Some indicators return data, some don't
        mock_adapter.query.side_effect = [
            mock_osint_result("GDP (current US$)", 25462700000000),
            mock_osint_result("GDP per capita (current US$)", None),  # No data
            mock_osint_result("Inflation, consumer prices (annual %)", 4.1),
            mock_osint_result("Unemployment, total (% of total labor force)", None),
            # Trade balance
            mock_osint_result(
                "External balance on goods and services (current US$)", -948100000000
            ),
            mock_osint_result("Population, total", 334900000),
        ]

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("United States")

        # Should still return formatted output
        assert "ECONOMIC CONTEXT" in result
        assert "COUNTRY: United States" in result
        assert "$25.46 trillion" in result  # GDP present
        assert "$76,330" not in result  # GDP per capita missing
        assert "4.1%" in result  # Inflation present
        # Unemployment missing - we don't check for specific % since we don't have it


@pytest.mark.asyncio
async def test_economic_context_country_not_found():
    """Test economic context with invalid country."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # All queries return NO_DATA
        no_data_result = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="gdp InvalidCountry",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )
        mock_adapter.query.return_value = no_data_result

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("InvalidCountry")

        assert "Country Not Found" in result
        assert "InvalidCountry" in result
        assert "Check the spelling" in result
        assert "ISO country code" in result


@pytest.mark.asyncio
async def test_economic_context_timeout():
    """Test economic context with timeout error."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()
        mock_adapter.query.side_effect = AdapterTimeoutError("worldbank", 15.0)

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("Germany")

        assert "Request Timed Out" in result
        assert "Germany" in result
        assert "Try again in a moment" in result
        assert "network connection" in result


@pytest.mark.asyncio
async def test_economic_context_rate_limited():
    """Test economic context with rate limit error (via AdapterError)."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Create an AdapterError with rate limit message
        error = AdapterError("worldbank", "Rate limit exceeded")
        mock_adapter.query.side_effect = error

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("Japan")

        assert "Service Temporarily Unavailable" in result
        assert "rate limiting" in result
        assert "Wait a few minutes" in result


@pytest.mark.asyncio
async def test_economic_context_rate_limited_status():
    """Test economic context with RATE_LIMITED result status."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Return RATE_LIMITED status from adapter
        rate_limited_result = OSINTResult(
            status=ResultStatus.RATE_LIMITED,
            query="gdp China",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )
        mock_adapter.query.return_value = rate_limited_result

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("China")

        assert "Service Temporarily Unavailable" in result
        assert "rate limiting" in result
        assert "Try again in a few minutes" in result


@pytest.mark.asyncio
async def test_economic_context_adapter_error():
    """Test economic context with general adapter error."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        error = AdapterError("worldbank", "Unknown error occurred")
        mock_adapter.query.side_effect = error

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("France")

        assert "Unable to Retrieve Data" in result
        assert "France" in result
        assert "Unknown error occurred" in result


@pytest.mark.asyncio
async def test_economic_context_unexpected_error():
    """Test economic context with unexpected exception."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()
        mock_adapter.query.side_effect = ValueError("Unexpected error")

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("India")

        assert "Error" in result
        assert "unexpected error" in result
        assert "India" in result


@pytest.mark.asyncio
async def test_economic_context_different_years(mock_osint_result):
    """Test economic context when indicators have different years."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Different years for different indicators
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

        mock_adapter.query.side_effect = [
            make_year_result("GDP (current US$)", 2000000000000, "2023"),
            make_year_result("GDP per capita (current US$)", 10000, "2023"),
            make_year_result("Inflation, consumer prices (annual %)", 5.0, "2022"),
            make_year_result(
                "Unemployment, total (% of total labor force)", 8.0, "2021"
            ),
            make_year_result(
                "External balance on goods and services (current US$)",
                50000000000, "2023"
            ),
            make_year_result("Population, total", 215000000, "2023"),
        ]

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("Brazil")

        # Should use the year from the first indicator
        assert "KEY INDICATORS (2023):" in result
        assert "Brazil" in result


@pytest.mark.asyncio
async def test_economic_context_positive_trade_balance(mock_osint_result):
    """Test formatting of positive trade balance."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Mock with positive trade balance
        mock_adapter.query.side_effect = [
            mock_osint_result("GDP (current US$)", 1500000000000),
            mock_osint_result("GDP per capita (current US$)", 50000),
            mock_osint_result("Inflation, consumer prices (annual %)", 2.0),
            mock_osint_result("Unemployment, total (% of total labor force)", 5.0),
            # Trade balance: +$100B
            mock_osint_result(
                "External balance on goods and services (current US$)", 100000000000
            ),
            mock_osint_result("Population, total", 50000000),
        ]

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("TestCountry")

        # Check for positive sign
        assert "+$100.0 billion" in result


@pytest.mark.asyncio
async def test_economic_context_country_alias():
    """Test that country aliases work correctly."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Mock successful response
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

        # Return success for GDP, NO_DATA for others to keep test simple
        no_data = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        mock_adapter.query.side_effect = [
            success_result,
            no_data,
            no_data,
            no_data,
            no_data,
            no_data,
        ]

        mock_get_wb.return_value = mock_adapter

        # Use "USA" alias instead of "United States"
        result = await call_economic_context("USA")

        # Should resolve to United States
        assert "United States" in result
        assert "ECONOMIC CONTEXT" in result


@pytest.mark.asyncio
async def test_economic_context_regional_aggregate_eu():
    """Test economic context for European Union regional aggregate (AC5)."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Mock successful response for EU
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

        no_data = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        mock_adapter.query.side_effect = [
            success_result,
            no_data,
            no_data,
            no_data,
            no_data,
            no_data,
        ]

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("European Union")

        assert "ECONOMIC CONTEXT" in result
        assert "European Union" in result
        assert "$16.64 trillion" in result


@pytest.mark.asyncio
async def test_economic_context_regional_aggregate_sub_saharan_africa():
    """Test economic context for Sub-Saharan Africa regional aggregate (AC5)."""
    with patch("ignifer.server._get_worldbank") as mock_get_wb:
        mock_adapter = AsyncMock()

        # Mock successful response for Sub-Saharan Africa
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

        no_data = OSINTResult(
            status=ResultStatus.NO_DATA,
            query="test",
            results=[],
            sources=[],
            retrieved_at=datetime.now(timezone.utc),
        )

        mock_adapter.query.side_effect = [
            success_result,
            no_data,
            no_data,
            no_data,
            no_data,
            no_data,
        ]

        mock_get_wb.return_value = mock_adapter

        result = await call_economic_context("Sub-Saharan Africa")

        assert "ECONOMIC CONTEXT" in result
        assert "Sub-Saharan Africa" in result
        assert "$1.86 trillion" in result
