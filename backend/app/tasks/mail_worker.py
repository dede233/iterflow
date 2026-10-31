"""Run with python -m app.tasks.mail_worker [--once]. No SMTP before commit."""

import argparse
import logging
import signal
import time

from app.core.database import SessionLocal
from app.services.delivery_service import DeliveryService

running = True


def stop(*_args):
    global running
    running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        try:
            with SessionLocal() as db:
                service = DeliveryService(db)
                service.expand()
                for _ in range(100):
                    if not running or not service.deliver_one():
                        break
        except Exception as exc:
            # Never log SMTP exception bodies, credentials or verification codes.
            logging.error("Notification worker failed: %s", type(exc).__name__)
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
