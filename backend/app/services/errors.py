"""Unified service-layer exception hierarchy (#32 P2 / audit P2).

Every service module raises these. Previously each of practice / question /
taxonomy_admin / exam / admin redefined its own ValidationError / NotFound /
ConflictError - five copies that could drift. Routers catch them and map to
HTTP statuses: ValidationError -> 422, NotFound -> 404, ConflictError -> 409.

``ServiceError`` is the common base. ``admin.py`` aliases it as ``AdminError``
so its router's ``except svc.AdminError`` keeps catching every subclass
without per-route changes.

The multiple inheritance (``ServiceError`` + ``ValueError``/``LookupError``)
preserves the original base classes so any ``isinstance(e, ValueError)`` /
``LookupError`` check elsewhere still holds.
"""


class ServiceError(Exception):
    """Base for all service-layer errors."""


class ValidationError(ServiceError, ValueError):
    """Input failed validation. Maps to HTTP 422."""


class NotFound(ServiceError, LookupError):
    """Target resource not found. Maps to HTTP 404."""


class ConflictError(ServiceError, ValueError):
    """Request conflicts with current state (e.g. wrong session phase).
    Maps to HTTP 409."""
