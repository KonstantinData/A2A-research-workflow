#!/usr/bin/env python3
"""Fail the build when deprecated Google OAuth environment names are present.

The workflow has moved to the v2 OAuth client exclusively.  Historical
configuration sometimes left secrets such as ``GOOGLE_CLIENT_ID_V2`` or
``GOOGLE_CLIENT_SECRET_JSON`` in the environment which silently re-enabled the
legacy flow.  This guard keeps CI honest by asserting those variables are not
set so production deployments do not depend on them either.
"""
from __future__ import annotations

import os
import sys
from textwrap import dedent

# Exact legacy keys we have encountered in previous deployments.
LEGACY_KEYS = {
    "GOOGLE_CLIENT_ID_V2",
    "GOOGLE_CLIENT_SECRET_V2",
    "GOOGLE_REFRESH_TOKEN_V2",
    "GOOGLE_CLIENT_SECRET_JSON",
    "GOOGLE_CLIENT_CREDENTIALS_JSON",
    "GOOGLE_OAUTH_CLIENT_JSON",
}

# Patterns for other discouraged variants.  Historically these were provided by
# copying the service-account style JSON exports or keeping both v1/v2 secrets
# around.  Rather than list every permutation, treat *_V2 and *_JSON endings as
# unsupported when attached to GOOGLE_* variables that relate to OAuth clients.
DISALLOWED_SUFFIXES = ("_V2", "_JSON")
ALLOWED_JSON_KEYS = {"GOOGLE_APPLICATION_CREDENTIALS"}

def main() -> int:
    offenders: list[str] = []

    for key, value in os.environ.items():
        if not value:
            continue
        if key in LEGACY_KEYS:
            offenders.append(key)
            continue
        if key in ALLOWED_JSON_KEYS:
            # Service account based integrations still rely on this variable.
            continue
        if key.startswith("GOOGLE_") and key.endswith(DISALLOWED_SUFFIXES):
            offenders.append(key)

    if offenders:
        offenders.sort()
        message = dedent(
            """
            ❌ Legacy Google OAuth environment variables detected. The v2 workflow
               intentionally ignores these keys; remove them from the execution
               environment to avoid falling back to the deprecated OAuth flow.

               Offending variables:
            """
        ).rstrip()
        print(message)
        for key in offenders:
            print(f"  • {key}")
        print(
            "\nSee README.md and ops/CONFIG.md for the supported GOOGLE_CLIENT_*"
            " configuration names."
        )
        return 1

    print(
        "✅ No legacy Google OAuth environment variables found; continuing with"
        " v2-only configuration."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
