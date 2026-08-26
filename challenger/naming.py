from __future__ import annotations

import hashlib
from datetime import date

from .models import Candidate

HUE_FAMILIES = [
    (15, "Red"),
    (45, "Orange"),
    (75, "Gold"),
    (105, "Chartreuse"),
    (155, "Green"),
    (195, "Teal"),
    (235, "Blue"),
    (275, "Indigo"),
    (315, "Violet"),
    (345, "Magenta"),
    (360, "Red"),
]

OBJECTS = {
    "Red": ["Launch Button", "Streaming Premiere", "Rush Shipping", "Lip Tint"],
    "Orange": ["Delivery App", "Airport Signage", "Vitamin Gummy", "Soft Launch"],
    "Gold": ["Loyalty Tier", "Hotel Lighting", "Snack Aisle", "Quarterly Optimism"],
    "Chartreuse": ["Wellness App", "Energy Drink", "Growth Hack", "Produce Sticker"],
    "Green": ["Expensive Olive Oil", "Finance Dashboard", "Boutique Hotel", "Plant Subscription"],
    "Teal": ["Telehealth Portal", "Pool Tile", "Travel Credit", "Smart Appliance"],
    "Blue": ["Quarterly Deck", "New EV", "Cloud Migration", "Airport Lounge"],
    "Indigo": ["Premium Plan", "Night Mode", "Festival Wristband", "Fintech Rebrand"],
    "Violet": ["Creator Economy", "Beauty Drop", "Gaming Bundle", "AI Keynote"],
    "Magenta": ["Subscription Cancel Button", "Beauty Launch", "Pop-Up Shop", "Streaming Ad"],
}

QUALIFIERS_DARK = ["After Hours", "Boardroom", "Midnight", "Private Beta"]
QUALIFIERS_LIGHT = ["Soft Focus", "Checkout Page", "Hotel Sheet", "Quiet Launch"]
QUALIFIERS_MUTED = ["Washed", "Understated", "Muted", "Almost Neutral"]
QUALIFIERS_VIVID = ["High-Intent", "Limited Edition", "Push Notification", "Campaign"]


def hue_family(hue: float) -> str:
    hue = hue % 360
    for threshold, name in HUE_FAMILIES:
        if hue < threshold:
            return name
    return "Red"


def _choose(items: list[str], seed: str, salt: str) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).digest()
    return items[int.from_bytes(digest[:4], "big") % len(items)]


def name_candidate(candidate: Candidate, target_date: date) -> str:
    lightness, chroma, hue = candidate.oklch
    family = hue_family(hue)
    seed = f"{target_date.isoformat()}:{candidate.hex}:{','.join(candidate.sectors)}"
    noun = _choose(OBJECTS[family], seed, "noun")

    if lightness < 0.38:
        qualifier = _choose(QUALIFIERS_DARK, seed, "qualifier")
    elif lightness > 0.82:
        qualifier = _choose(QUALIFIERS_LIGHT, seed, "qualifier")
    elif chroma < 0.055:
        qualifier = _choose(QUALIFIERS_MUTED, seed, "qualifier")
    elif chroma > 0.16:
        qualifier = _choose(QUALIFIERS_VIVID, seed, "qualifier")
    else:
        return f"{noun} {family}"

    # Avoid awkward duplicates such as "Campaign Launch Button Red".
    if qualifier.lower() in noun.lower():
        return f"{noun} {family}"
    return f"{qualifier} {noun} {family}"
