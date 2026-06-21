"""Soft-delete query helpers.

Reads against soft-deletable models should scope with not_deleted(model).
To include soft-deleted rows (admin views), simply omit the filter.
"""

from sqlalchemy.orm import DeclarativeBase


def not_deleted(model: type[DeclarativeBase]):
    """Return a filter clause excluding soft-deleted rows.

    Raises AttributeError if the model lacks a deleted_at column, which surfaces
    misuse early rather than silently returning an unscoped query.
    """
    return model.deleted_at.is_(None)
