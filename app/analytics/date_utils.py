"""
Date range parsing, validation, and boundary calculation for OpsLens.
Uses half-open intervals [start_bound, end_bound) with an exclusive upper bound
(start of the next day) to safely include all timestamps, including those with fractional seconds.
"""

from datetime import datetime, timedelta

VALID_PRESETS = ('7d', '30d', '90d', 'all', 'custom')


def parse_date_range(preset=None, start_date_str=None, end_date_str=None, now=None):
    """
    Parses and validates a date filter.
    Returns normalized bounds where the end date is inclusive of the entire day by setting
    the exclusive end_bound to the start of the following day (00:00:00).

    Parameters:
    - preset: str in ('7d', '30d', '90d', 'all', 'custom')
    - start_date_str: str 'YYYY-MM-DD'
    - end_date_str: str 'YYYY-MM-DD'
    - now: datetime instance (optional, for deterministic unit tests)

    Returns a dict with:
    - preset: normalized preset name ('7d', '30d', '90d', 'all', 'custom')
    - start_bound: ISO timestamp 'YYYY-MM-DD 00:00:00' or None
    - end_bound: ISO timestamp of next day 'YYYY-MM-DD 00:00:00' (exclusive) or None
    - start_date: original/parsed 'YYYY-MM-DD' string or ''
    - end_date: original/parsed 'YYYY-MM-DD' string or ''
    - is_custom: bool
    - error: validation warning message if invalid/reversed dates were provided
    """
    if now is None:
        now = datetime.now()

    error = None
    preset = (preset or '').strip().lower()

    # Determine if custom range was explicitly requested or inferred from date inputs
    if preset == 'custom' or (start_date_str and end_date_str):
        start_date_str = (start_date_str or '').strip()
        end_date_str = (end_date_str or '').strip()

        if not start_date_str or not end_date_str:
            error = "Both start date and end date are required for custom date range."
            return _default_all(error)

        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            error = "Invalid date format. Please use YYYY-MM-DD."
            return _default_all(error)

        if start_dt > end_dt:
            error = f"Reversed date range: Start date ({start_date_str}) cannot be after end date ({end_date_str})."
            return _default_all(error)

        next_day = end_dt + timedelta(days=1)
        return {
            'preset': 'custom',
            'start_bound': start_dt.strftime('%Y-%m-%d 00:00:00'),
            'end_bound': next_day.strftime('%Y-%m-%d 00:00:00'),
            'start_date': start_date_str,
            'end_date': end_date_str,
            'is_custom': True,
            'error': None
        }

    tomorrow_bound = (now + timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')

    if preset == '7d':
        start_dt = now - timedelta(days=7)
        return {
            'preset': '7d',
            'start_bound': start_dt.strftime('%Y-%m-%d 00:00:00'),
            'end_bound': tomorrow_bound,
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': now.strftime('%Y-%m-%d'),
            'is_custom': False,
            'error': None
        }

    if preset == '30d':
        start_dt = now - timedelta(days=30)
        return {
            'preset': '30d',
            'start_bound': start_dt.strftime('%Y-%m-%d 00:00:00'),
            'end_bound': tomorrow_bound,
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': now.strftime('%Y-%m-%d'),
            'is_custom': False,
            'error': None
        }

    if preset == '90d':
        start_dt = now - timedelta(days=90)
        return {
            'preset': '90d',
            'start_bound': start_dt.strftime('%Y-%m-%d 00:00:00'),
            'end_bound': tomorrow_bound,
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': now.strftime('%Y-%m-%d'),
            'is_custom': False,
            'error': None
        }

    return _default_all(None)


def _default_all(error=None):
    """Fallback helper when 'all' is selected or when custom date validation fails."""
    return {
        'preset': 'all',
        'start_bound': None,
        'end_bound': None,
        'start_date': '',
        'end_date': '',
        'is_custom': False,
        'error': error
    }


def build_date_where_clause(column_name, date_filter):
    """
    Constructs a parameterized SQL condition and parameter list for a given timestamp column.
    Uses half-open interval [start_bound, end_bound) with an exclusive upper boundary (< end_bound).

    Example:
    clause, params = build_date_where_clause('t.created_at', date_filter)
    Returns: ('t.created_at >= ? AND t.created_at < ?', ['2026-10-15 00:00:00', '2026-10-19 00:00:00'])
    or: ('1=1', []) if no bounds.
    """
    if date_filter['start_bound'] and date_filter['end_bound']:
        return f"{column_name} >= ? AND {column_name} < ?", [date_filter['start_bound'], date_filter['end_bound']]
    elif date_filter['start_bound']:
        return f"{column_name} >= ?", [date_filter['start_bound']]
    elif date_filter['end_bound']:
        return f"{column_name} < ?", [date_filter['end_bound']]
    return "1=1", []
