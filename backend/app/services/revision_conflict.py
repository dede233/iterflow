from typing import Any


def revision_conflict_data(item: Any | None) -> dict[str, int | str | None]:
    """Return only the shared CAS metadata; detail GET owns object visibility."""
    return {
        "current_revision": item.revision if item is not None else None,
        "current_updated_at": (
            item.updated_at.isoformat() if item is not None and item.updated_at else None
        ),
        "current_updated_by": item.updated_by if item is not None else None,
    }
