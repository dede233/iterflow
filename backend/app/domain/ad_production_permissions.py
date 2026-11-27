from typing import NamedTuple

from app.models.enums import AdProductionKind


class AdProductionPermissions(NamedTuple):
    view: str
    create: str
    edit: str


AD_PRODUCTION_PERMISSIONS = {
    AdProductionKind.MATERIAL: AdProductionPermissions(
        "ops.ad_production.view", "ops.ad_production.create", "ops.ad_production.edit"
    ),
    AdProductionKind.MERCHANT_AD: AdProductionPermissions(
        "ops.merchant_ad.view", "ops.merchant_ad.create", "ops.merchant_ad.edit"
    ),
}


def viewable_ad_production_kinds(permissions: set[str]) -> set[AdProductionKind]:
    return {
        kind
        for kind, codes in AD_PRODUCTION_PERMISSIONS.items()
        if "*" in permissions or codes.view in permissions
    }
