"""Custom exceptions for jsonlproc."""


class JsonlProcError(Exception):
    """Base exception for all jsonlproc errors.

    Args:
        message: Human-readable error description.
    """


class ParseError(JsonlProcError):
    """Raised when a filter expression cannot be parsed.

    Args:
        message: Description of the parse failure.
        expression: The expression string that caused the error.
        position: Optional character position in the expression.
    """

    def __init__(self, message: str, expression: str = "", position: int = -1) -> None:
        self.expression = expression
        self.position = position
        detail = f" at position {position}" if position >= 0 else ""
        full_msg = f"{message}{detail}"
        if expression:
            full_msg += f"\n  Expression: {expression}"
        super().__init__(full_msg)


class FieldError(JsonlProcError):
    """Raised when a field is missing or cannot be accessed.

    Args:
        message: Description of the field access error.
        field: The field path that caused the error.
    """

    def __init__(self, message: str, field: str = "") -> None:
        self.field = field
        full_msg = f"{message}"
        if field:
            full_msg += f" (field: '{field}')"
        super().__init__(full_msg)


class AggregationError(JsonlProcError):
    """Raised when aggregation configuration or execution fails.

    Args:
        message: Description of the aggregation error.
    """
