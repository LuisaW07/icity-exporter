"""Custom exceptions for the icity client."""


class ICityError(Exception):
    """Base exception for all icity errors."""
    pass


class LoginError(ICityError):
    """Login failed — wrong email/password or site unreachable."""
    pass


class NotAuthenticatedError(ICityError):
    """Operation requires login but client is in anonymous mode."""
    pass


class EntryNotFoundError(ICityError):
    """The requested diary entry does not exist or is not accessible."""
    pass
