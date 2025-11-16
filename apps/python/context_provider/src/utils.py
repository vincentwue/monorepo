import datetime


def log(msg: str) -> None:
    """Timestamped console log."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [LOG] {msg}")
