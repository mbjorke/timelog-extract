"""Backward-compatible wrapper; prefer `core.calibration.screen_time_gap`."""

from core.calibration.screen_time_gap import DayGap, analyze_screen_time_gaps

__all__ = ["DayGap", "analyze_screen_time_gaps"]

