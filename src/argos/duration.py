import re

_TOKEN = re.compile(r"(\d+(?:\.\d+)?)([hms])", re.I)


def parse_duration(raw: str) -> float:
    text = raw.strip().lower()
    if not text:
        raise ValueError("empty duration")
    if text.isdigit():
        return float(text)
    if _TOKEN.fullmatch(text) or _TOKEN.match(text):
        total = 0.0
        pos = 0
        for match in _TOKEN.finditer(text):
            if match.start() != pos:
                raise ValueError(f"invalid duration {raw!r}")
            value = float(match.group(1))
            unit = match.group(2)
            if unit == "h":
                total += value * 3600
            elif unit == "m":
                total += value * 60
            else:
                total += value
            pos = match.end()
        if pos != len(text):
            raise ValueError(f"invalid duration {raw!r}")
        if total <= 0:
            raise ValueError(f"duration must be > 0: {raw!r}")
        return total
    raise ValueError(f"invalid duration {raw!r} (use 8h, 90m, 45s, 1h30m)")
