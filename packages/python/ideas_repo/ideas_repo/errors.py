"""Domain-level errors for the ideas repository."""


class IdeaNotFoundError(Exception):
    """Raised when an idea node cannot be located."""


class PermissionDeniedError(Exception):
    """Raised when a user lacks permissions to perform an action."""
