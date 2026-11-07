"""Product version of the PsyFi package.

Read ``docs/VERSIONING.md`` before changing this. The API contract stays
``v1``. The frozen OpenAPI document version and the session ``engine_version``
default stay ``0.1.0``.
"""

from pathlib import Path

__version__ = Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()
