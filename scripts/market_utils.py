"""
Market time utilities for A-share trading hours.

A-share trading sessions: Mon-Fri 9:30-11:30, 13:00-15:00
"""
from datetime import datetime, time


MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


def is_market_open(dt=None) -> bool:
    """Check if the market is currently open for trading.

    A-shares trade Mon-Fri during 9:30-11:30 and 13:00-15:00.
    Does not account for holidays.

    Args:
        dt: Optional datetime to check. Uses current time if None.

    Returns:
        True if within trading hours on a weekday, False otherwise.
    """
    if dt is None:
        dt = datetime.now()

    # Check weekday (Mon=0, Sun=6)
    if dt.weekday() >= 5:
        return False

    t = dt.time()
    return (MORNING_START <= t <= MORNING_END) or (AFTERNOON_START <= t <= AFTERNOON_END)


def get_market_status(dt=None) -> str:
    """Get current market status string.

    Args:
        dt: Optional datetime to check. Uses current time if None.

    Returns:
        'open' if in trading hours on a weekday,
        'closed' if a weekday but outside trading hours,
        'non_trading_day' if weekend.
    """
    if dt is None:
        dt = datetime.now()

    if dt.weekday() >= 5:
        return 'non_trading_day'

    t = dt.time()
    if (MORNING_START <= t <= MORNING_END) or (AFTERNOON_START <= t <= AFTERNOON_END):
        return 'open'

    return 'closed'
