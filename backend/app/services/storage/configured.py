from app.core.config import Settings
from app.models.enums import StorageDriver
from app.services.storage.base import StorageService
from app.services.storage.factory import create_storage_service


def create_configured_storage(
    settings: Settings, driver: StorageDriver | str | None = None
) -> StorageService:
    selected_driver = driver or settings.storage_driver
    secret = settings.s3_secret_key
    return create_storage_service(
        selected_driver,
        local_storage_path=settings.local_storage_root,
        s3_endpoint=settings.s3_endpoint,
        s3_access_key=settings.s3_access_key,
        s3_secret_key=secret.get_secret_value() if secret else None,
        s3_bucket=settings.s3_bucket,
        s3_region=settings.s3_region,
    )
