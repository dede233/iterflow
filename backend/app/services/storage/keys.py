from pathlib import PurePosixPath


class InvalidStorageKeyError(ValueError):
    pass


def validate_storage_key(storage_key: str) -> str:
    """Validate an opaque, application-generated object key.

    Keys use POSIX separators for both local and S3 drivers. Rejecting Windows
    separators as well keeps a key safe if the local driver is used on Windows.
    """

    if not storage_key or "\x00" in storage_key or "\\" in storage_key:
        raise InvalidStorageKeyError("invalid storage key")

    path = PurePosixPath(storage_key)
    raw_parts = storage_key.split("/")
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        raise InvalidStorageKeyError("storage key must be a relative canonical path")

    return path.as_posix()
