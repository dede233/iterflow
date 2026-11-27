HISTORICAL_AD_PRODUCTION_ROLE_CODES = frozenset(
    {"AD_PRODUCTION_CREATOR", "AD_PRODUCTION_COMPLETER"}
)


def is_historical_ad_production_role(code: str, *, is_system: bool) -> bool:
    return is_system and code in HISTORICAL_AD_PRODUCTION_ROLE_CODES
