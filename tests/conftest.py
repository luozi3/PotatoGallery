"""Shared test fixtures and constants."""
import secrets

# Random password for test users — changes each test run,
# avoids hardcoding real-looking secrets in source code.
TEST_PASSWORD = f"test-{secrets.token_urlsafe(16)}"
