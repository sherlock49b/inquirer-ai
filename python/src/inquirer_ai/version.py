from __future__ import annotations

_cached_version: str | None = None


def get_version() -> str:
    """Return the installed package version, cached after first lookup.

    Falls back to "0.0.0" when the package is not installed (e.g. running
    from a source tree without an installed distribution) so that lookups
    never raise PackageNotFoundError.
    """
    global _cached_version
    if _cached_version is None:
        from importlib.metadata import PackageNotFoundError, version

        try:
            _cached_version = version("inquirer-ai")
        except PackageNotFoundError:
            _cached_version = "0.0.0"
    return _cached_version
