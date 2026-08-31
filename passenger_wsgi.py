"""Phusion Passenger entrypoint.

Passenger >= 6 auto-detects an ASGI3 callable (an object taking (scope, receive, send)), so
exposing the FastAPI app directly as `application` works on modern Passenger. There is no
reliable way to introspect the host's Passenger version from inside this script, so older,
WSGI-only Passenger needs an explicit operator opt-in: set PASSENGER_FORCE_WSGI=1 in the
environment (e.g. in the shared host's control panel) to wrap the app with a2wsgi instead.

If a fresh deploy fails, check the Passenger error log first — if it complains about the
app object not being callable the way it expects, that's the signal to set this flag.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app as _asgi_app  # noqa: E402

if os.environ.get("PASSENGER_FORCE_WSGI", "").lower() in ("1", "true", "yes"):
    from a2wsgi import ASGIMiddleware

    application = ASGIMiddleware(_asgi_app)
else:
    application = _asgi_app
