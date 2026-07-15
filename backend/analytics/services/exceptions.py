"""Custom exceptions for analytics services.

Each carries structured context (which filters were used, a suggestion
for what to do next) so views.py can return a precise, actionable error
message instead of a generic "An error occurred" -- e.g. "No exam results
recorded for this academic year yet" rather than a bare 500.
"""


class AnalyticsError(Exception):
    """Base class for all analytics service errors."""

    def __init__(self, message=None, filters=None, suggestion=None):
        self.filters = filters or {}
        self.suggestion = suggestion or ''
        self.message = message or self.default_message()
        super().__init__(self.message)

    def default_message(self):
        return 'An analytics error occurred.'

    def to_response_data(self):
        return {
            'error': self.message,
            'filters': self.filters,
            'suggestion': self.suggestion,
        }


class InsufficientDataError(AnalyticsError):
    """Raised when a query is well-formed but there's simply no data yet
    (e.g. no exam results entered for the requested term)."""

    def default_message(self):
        return 'Not enough data available for this request.'

    def to_response_data(self):
        return {
            **super().to_response_data(),
            "empty": True,
        }

class InvalidFilterError(AnalyticsError):
    """Raised when filters are malformed or contradictory in a way that
    basic serializer validation wouldn't catch (e.g. a classroom_id that
    doesn't belong to the requested tenant)."""

    def default_message(self):
        return 'One or more filters are invalid.'
