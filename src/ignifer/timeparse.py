"""Time range parser for GDELT API parameters."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Regex patterns for natural language time ranges
LAST_N_PATTERN = re.compile(
    r"last\s+(\d+)\s+(hour|hours|day|days|week|weeks|month|months)",
    re.IGNORECASE
)
N_UNIT_PATTERN = re.compile(
    r"^(\d+)\s+(hour|hours|day|days|week|weeks|month|months)$",
    re.IGNORECASE
)
DATE_RANGE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE
)

# Unit to GDELT timespan suffix mapping
UNIT_SUFFIX_MAP = {
    "hour": "h", "hours": "h",
    "day": "d", "days": "d",
    "week": "w", "weeks": "w",
    "month": "m", "months": "m",
}


@dataclass
class TimeRangeResult:
    """Result of parsing a time range string."""

    gdelt_timespan: str | None = None  # e.g., "48h", "7d"
    start_datetime: str | None = None  # YYYYMMDDHHMMSS format
    end_datetime: str | None = None    # YYYYMMDDHHMMSS format
    error: str | None = None           # User-friendly error message

    @property
    def is_valid(self) -> bool:
        """Check if the result is valid (no error)."""
        return self.error is None


def _unit_to_timespan(n: int, unit: str) -> TimeRangeResult:
    """Convert a numeric value and time unit to a GDELT timespan.

    Args:
        n: Number of units
        unit: Time unit (hour, hours, day, days, week, weeks, month, months)

    Returns:
        TimeRangeResult with gdelt_timespan set
    """
    suffix = UNIT_SUFFIX_MAP.get(unit.lower())
    if suffix:
        return TimeRangeResult(gdelt_timespan=f"{n}{suffix}")
    return TimeRangeResult(error=f"Unknown time unit: {unit}")


def parse_time_range(time_range: str) -> TimeRangeResult:
    """Parse user time range into GDELT parameters.

    Supports natural language patterns like:
    - "last 24 hours", "last 48 hours"
    - "last 7 days", "last 30 days"
    - "this week", "last week"
    - "2026-01-01 to 2026-01-08" (ISO date range)
    - "1 hour", "3 days"

    Args:
        time_range: Natural language time range string.

    Returns:
        TimeRangeResult with either gdelt_timespan or datetime params.
    """
    time_range = time_range.strip()
    time_range_lower = time_range.lower()

    # Handle "this week" -> last 7 days
    if time_range_lower == "this week":
        return TimeRangeResult(gdelt_timespan="7d")

    # Handle "last week" -> use absolute dates (7-14 days ago)
    if time_range_lower == "last week":
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=14)
        end = now - timedelta(days=7)
        return TimeRangeResult(
            start_datetime=start.strftime("%Y%m%d%H%M%S"),
            end_datetime=end.strftime("%Y%m%d%H%M%S")
        )

    # Handle "last N hours/days/weeks/months" or "N hours/days/weeks/months"
    for pattern in (LAST_N_PATTERN, N_UNIT_PATTERN):
        match = pattern.match(time_range)
        if match:
            return _unit_to_timespan(int(match.group(1)), match.group(2))

    # Handle ISO date range "YYYY-MM-DD to YYYY-MM-DD"
    match = DATE_RANGE_PATTERN.match(time_range)
    if match:
        start_str, end_str = match.group(1), match.group(2)

        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_date = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

            # Validate start < end
            if start_date >= end_date:
                return TimeRangeResult(
                    error=f"Start date must be before end date: {start_str} >= {end_str}"
                )

            return TimeRangeResult(
                start_datetime=start_date.strftime("%Y%m%d%H%M%S"),
                end_datetime=end_date.strftime("%Y%m%d%H%M%S")
            )
        except ValueError as e:
            return TimeRangeResult(error=f"Invalid date format: {e}")

    # No pattern matched
    return TimeRangeResult(
        error=f"Unrecognized time range format: {time_range}"
    )


__all__ = ["TimeRangeResult", "parse_time_range"]
