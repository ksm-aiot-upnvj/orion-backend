import uuid


def generate_uuid7() -> uuid.UUID:
    """Generate a RFC 9562 compliant UUIDv7 with time-ordered monotonic timestamp."""
    return uuid.uuid7()
