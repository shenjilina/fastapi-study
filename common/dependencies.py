"""Global dependency helpers."""


def strip_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()
