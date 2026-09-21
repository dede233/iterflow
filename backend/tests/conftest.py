import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://iterflow@localhost/iterflow_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET", "phase-zero-test-secret-that-is-at-least-32-characters")
os.environ.setdefault("JWT_ACCESS_TTL_MINUTES", "30")
os.environ.setdefault("JWT_REFRESH_TTL_DAYS", "14")
os.environ.setdefault("STORAGE_DRIVER", "local")
os.environ.setdefault("LOCAL_STORAGE_PATH", "./data/test-uploads")
