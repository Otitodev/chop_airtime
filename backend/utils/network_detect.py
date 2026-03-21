"""Nigerian phone number prefix → network detection."""

from typing import Optional

_PREFIX_MAP: dict[str, list[str]] = {
    "MTN": ["0803", "0806", "0703", "0706", "0813", "0816", "0810", "0814", "0903", "0906"],
    "Airtel": ["0802", "0808", "0708", "0812", "0902"],
    "Glo": ["0805", "0807", "0705", "0815", "0905"],
    "9mobile": ["0809", "0817", "0818", "0908", "0909"],
}

# Build reverse lookup: prefix → network name
_LOOKUP: dict[str, str] = {
    prefix: network
    for network, prefixes in _PREFIX_MAP.items()
    for prefix in prefixes
}

# VTpass serviceID mapping
_VTPASS_SERVICE_ID: dict[str, str] = {
    "MTN": "mtn",
    "Airtel": "airtel",
    "Glo": "glo",
    "9mobile": "etisalat",
}


def detect_network(phone: str) -> Optional[str]:
    """
    Return the network name for a Nigerian phone number, or None if unrecognised.

    Accepts 11-digit numbers starting with 0 (e.g. '08031234567').
    """
    normalised = phone.strip()
    if len(normalised) != 11 or not normalised.isdigit():
        return None
    prefix = normalised[:4]
    return _LOOKUP.get(prefix)


def is_valid_nigerian_number(phone: str) -> bool:
    """Return True if phone is an 11-digit Nigerian mobile number with a known prefix."""
    return detect_network(phone) is not None


def get_vtpass_service_id(network: str) -> Optional[str]:
    """Return the VTpass serviceID string for a given network name."""
    return _VTPASS_SERVICE_ID.get(network)
