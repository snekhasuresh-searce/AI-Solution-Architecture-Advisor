"""Test settings, applied before any advisor module reads its configuration.

Values set here win over backend/.env (python-dotenv never overrides existing
variables), so the suite never touches a real database or real Google sign-in.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="advisor-tests-")
os.environ.update({
    "ADVISOR_PROVIDER": "mock",
    "ADVISOR_DATABASE_URL": "",
    "ADVISOR_DB_PATH": os.path.join(_TMP, "app.sqlite"),
    "ADVISOR_OUTPUT_DIR": os.path.join(_TMP, "outputs"),
    "ADVISOR_AUTH_MODE": "dev",
    "ADVISOR_ALLOWED_DOMAINS": "searce.com",
    "ADVISOR_ADMIN_EMAILS": "boss@searce.com",
    "GOOGLE_OAUTH_CLIENT_ID": "test-client.apps.googleusercontent.com",
    "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
    "ADVISOR_FRONTEND_URL": "http://localhost:5173",
})
