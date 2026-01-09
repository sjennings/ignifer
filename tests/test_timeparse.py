"""Unit tests for time range parser."""

import pytest
from datetime import datetime, timezone

from ignifer.timeparse import parse_time_range, TimeRangeResult


class TestParseTimeRange:
    """Test suite for parse_time_range function."""

    def test_parse_last_n_hours_valid(self):
        """Test parsing 'last N hours' format."""
        result = parse_time_range("last 24 hours")
        assert result.is_valid
        assert result.gdelt_timespan == "24h"
        assert result.error is None

        result = parse_time_range("last 48 hours")
        assert result.is_valid
        assert result.gdelt_timespan == "48h"

        result = parse_time_range("last 1 hour")
        assert result.is_valid
        assert result.gdelt_timespan == "1h"

    def test_parse_last_n_days_valid(self):
        """Test parsing 'last N days' format."""
        result = parse_time_range("last 7 days")
        assert result.is_valid
        assert result.gdelt_timespan == "7d"
        assert result.error is None

        result = parse_time_range("last 30 days")
        assert result.is_valid
        assert result.gdelt_timespan == "30d"

        result = parse_time_range("last 1 day")
        assert result.is_valid
        assert result.gdelt_timespan == "1d"

    def test_parse_last_n_weeks_valid(self):
        """Test parsing 'last N weeks' format."""
        result = parse_time_range("last 2 weeks")
        assert result.is_valid
        assert result.gdelt_timespan == "2w"

        result = parse_time_range("last 1 week")
        assert result.is_valid
        assert result.gdelt_timespan == "1w"

    def test_parse_last_n_months_valid(self):
        """Test parsing 'last N months' format."""
        result = parse_time_range("last 3 months")
        assert result.is_valid
        assert result.gdelt_timespan == "3m"

        result = parse_time_range("last 1 month")
        assert result.is_valid
        assert result.gdelt_timespan == "1m"

    def test_parse_this_week(self):
        """Test parsing 'this week' format."""
        result = parse_time_range("this week")
        assert result.is_valid
        assert result.gdelt_timespan == "7d"
        assert result.error is None

    def test_parse_last_week(self):
        """Test parsing 'last week' format - should return datetime params."""
        result = parse_time_range("last week")
        assert result.is_valid
        assert result.start_datetime is not None
        assert result.end_datetime is not None
        assert result.gdelt_timespan is None
        assert result.error is None

        # Validate format YYYYMMDDHHMMSS
        assert len(result.start_datetime) == 14
        assert len(result.end_datetime) == 14

    def test_parse_iso_date_range(self):
        """Test parsing ISO date range format."""
        result = parse_time_range("2026-01-01 to 2026-01-08")
        assert result.is_valid
        assert result.start_datetime == "20260101000000"
        assert result.end_datetime == "20260108000000"
        assert result.gdelt_timespan is None
        assert result.error is None

    def test_parse_iso_date_range_invalid_order(self):
        """Test ISO date range with start >= end returns error."""
        result = parse_time_range("2026-01-08 to 2026-01-01")
        assert not result.is_valid
        assert result.error is not None
        assert "Start date must be before end date" in result.error

    def test_parse_iso_date_range_invalid_format(self):
        """Test ISO date range with invalid date format."""
        result = parse_time_range("2026-13-01 to 2026-13-08")
        assert not result.is_valid
        assert result.error is not None
        assert "Invalid date format" in result.error

    def test_parse_invalid_format_returns_error(self):
        """Test invalid format returns error."""
        result = parse_time_range("yesterday")
        assert not result.is_valid
        assert result.error is not None
        assert "Unrecognized time range format" in result.error

        result = parse_time_range("not a time range")
        assert not result.is_valid
        assert result.error is not None

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive."""
        result = parse_time_range("LAST 24 HOURS")
        assert result.is_valid
        assert result.gdelt_timespan == "24h"

        result = parse_time_range("Last 7 Days")
        assert result.is_valid
        assert result.gdelt_timespan == "7d"

        result = parse_time_range("THIS WEEK")
        assert result.is_valid
        assert result.gdelt_timespan == "7d"

    def test_parse_n_unit_pattern(self):
        """Test parsing 'N hours/days/weeks' without 'last' prefix."""
        result = parse_time_range("1 hour")
        assert result.is_valid
        assert result.gdelt_timespan == "1h"

        result = parse_time_range("3 days")
        assert result.is_valid
        assert result.gdelt_timespan == "3d"

        result = parse_time_range("2 weeks")
        assert result.is_valid
        assert result.gdelt_timespan == "2w"

    def test_parse_whitespace_stripping(self):
        """Test that whitespace is properly handled."""
        result = parse_time_range("  last 24 hours  ")
        assert result.is_valid
        assert result.gdelt_timespan == "24h"

    def test_time_range_result_is_valid_property(self):
        """Test TimeRangeResult.is_valid property."""
        valid_result = TimeRangeResult(gdelt_timespan="24h")
        assert valid_result.is_valid

        invalid_result = TimeRangeResult(error="Some error")
        assert not invalid_result.is_valid

        empty_result = TimeRangeResult()
        assert empty_result.is_valid  # No error means valid
