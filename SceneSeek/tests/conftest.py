import os

# Tests exercise the queue without a background worker racing them.
os.environ.setdefault("RUN_EMBEDDED_WORKER", "false")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
