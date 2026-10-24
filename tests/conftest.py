"""Automated tests must never inherit the paid local development opt-in."""

import os

os.environ["APP_ENV"] = "production"
os.environ["LOCAL_OPENROUTER_ENABLED"] = "false"
