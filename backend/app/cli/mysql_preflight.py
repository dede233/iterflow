import argparse
import json

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine
from app.core.mysql_preflight import validate_mysql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--empty", action="store_true")
    args = parser.parse_args()
    if engine.dialect.name != "mysql":
        raise SystemExit("MySQL preflight requires mysql+pymysql DATABASE_URL")
    try:
        with engine.connect() as connection:
            result = validate_mysql(connection, empty=args.empty)
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except SQLAlchemyError:
        raise SystemExit(
            "Database preflight failed; check protected connection configuration and privileges"
        ) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
