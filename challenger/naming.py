from __future__ import annotations

import hashlib

from challenger.models import Candidate


PREFIXES = {
    "Red": ["Signal", "After-Hours", "Poster Ink", "Emergency Exit"],
    "Red-Orange": ["Kiln", "Transit Map", "Festival Wristband", "Late Checkout"],
    "Orange": ["Airport Signage", "Studio Ceramic", "Launch Day", "Apricot Vinyl"],
    "Amber": ["Gallery Light", "Archive Label", "Cinema Lobby", "Honeyed Glass"],
    "Yellow": ["Highlighter", "Morning Edition", "Soft Launch", "Sunlit Receipt"],
    "Yellow-Green": ["New Growth", "Digital Moss", "Gallery Exit", "Signal Garden"],
    "Chartreuse": ["Underground Flyer", "Electric Herb", "Night Market", "Acid Tennis"],
    "Green": ["Open Studio", "Transit Garden", "Independent Press", "Soft Hardware"],
    "Teal": ["Public Pool", "New Interface", "Sea Glass", "Night Train"],
    "Cyan": ["Prototype", "Cold Screen", "Festival Laser", "Open Water"],
    "Blue": ["Cloud Migration", "Museum Wall", "Quarterly Deck", "Platform"],
    "Indigo": ["Late-Night App", "Ink Wash", "Deep Link", "Stage Curtain"],
    "Violet": ["Private Beta", "Creator Economy", "Gallery Dusk", "Limited Edition"],
    "Magenta": ["Pop-Up", "New Wave", "Beauty Counter", "Digital Bloom"],
    "Rose": ["Editorial", "Soft Power", "Archive Blush", "Studio Dust"],
    "Black": ["Black"],
    "Charcoal": ["Charcoal"],
    "Gray": ["Gray"],
    "Light Gray": ["Light Gray"],
    "White": ["White"],
}


def creative_name(family: str, hex_value: str, date: str, dominant_domain: str = "") -> str:
    options = PREFIXES.get(family, ["Cultural Signal"])
    if len(options) == 1 and options[0] == family:
        return family
    digest = hashlib.sha256(f"{date}:{hex_value}:{dominant_domain}".encode()).digest()
    prefix = options[digest[0] % len(options)]
    return f"{prefix} {family}".upper()
