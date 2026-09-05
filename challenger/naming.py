from __future__ import annotations

import hashlib
from datetime import date

from .models import Candidate
from .recurrence import color_family_name


OBJECTS = {
    "Rose": ["Beauty Launch", "Streaming Ad", "Pop-Up Shop", "Campaign Ribbon"],
    "Red": ["Launch Button", "Streaming Premiere", "Rush Shipping", "Lip Tint"],
    "Red-Orange": ["Delivery App", "Sale Banner", "Transit Poster", "Soft Launch"],
    "Orange": ["Airport Signage", "Vitamin Gummy", "Delivery App", "Soft Launch"],
    "Amber": ["Hotel Lighting", "Snack Aisle", "Loyalty Tier", "Quarterly Optimism"],
    "Gold": ["Loyalty Tier", "Hotel Lighting", "Snack Aisle", "Quarterly Optimism"],
    "Ochre": ["Editorial Paper", "Hotel Lighting", "Packaging Board", "Market Tote"],
    "Yellow": ["Checkout Highlight", "Summer Campaign", "Product Sticker", "Launch Deck"],
    "Yellow-Green": ["Produce Sticker", "Energy Drink", "Growth Chart", "Wellness App"],
    "Chartreuse": ["Wellness App", "Energy Drink", "Growth Hack", "Produce Sticker"],
    "Olive Green": ["Expensive Olive Oil", "Boutique Hotel", "Plant Subscription", "Travel Case"],
    "Sage Green": ["Quiet Hotel", "Skincare Drop", "Kitchen Cabinet", "Wellness Brand"],
    "Green": ["Finance Dashboard", "Boutique Hotel", "Plant Subscription", "Grocery Aisle"],
    "Slate Teal": ["Telehealth Portal", "Pool Tile", "Travel Credit", "Smart Appliance"],
    "Teal": ["Telehealth Portal", "Pool Tile", "Travel Credit", "Smart Appliance"],
    "Cyan Blue": ["Travel App", "Product Launch", "Cloud Console", "Pool Sign"],
    "Blue": ["Quarterly Deck", "New EV", "Cloud Migration", "Airport Lounge"],
    "Slate Blue": ["Conference Deck", "Hotel Carpet", "Device Launch", "Travel Portal"],
    "Indigo": ["Premium Plan", "Night Mode", "Festival Wristband", "Fintech Rebrand"],
    "Violet": ["Creator Economy", "Beauty Drop", "Gaming Bundle", "AI Keynote"],
    "Dusty Magenta": ["Beauty Editorial", "Hotel Textile", "Packaging Drop", "Streaming Poster"],
    "Magenta": ["Subscription Button", "Beauty Launch", "Pop-Up Shop", "Streaming Ad"],
    "Dusty Rose": ["Skincare Carton", "Editorial Backdrop", "Hotel Linen", "Beauty Campaign"],
}

QUALIFIERS_DARK = ["After Hours", "Boardroom", "Midnight", "Private Beta"]
QUALIFIERS_LIGHT = ["Soft Focus", "Checkout Page", "Hotel Sheet", "Quiet Launch"]
QUALIFIERS_MUTED = ["Washed", "Understated", "Muted", "Almost Neutral"]
QUALIFIERS_VIVID = ["High-Intent", "Limited Edition", "Push Notification", "Campaign"]

NEUTRAL_OBJECTS = {
    "Black": ["Night Mode", "Streaming Interface", "Studio Backdrop", "Luxury Packaging"],
    "Charcoal": ["Creator Dashboard", "Product Launch", "Hotel Lobby", "Performance Gear"],
    "Gray": ["Checkout Flow", "Device Mockup", "Office Interior", "Subscription Screen"],
    "Light Gray": ["Cloud Interface", "Retail Backdrop", "Packaging Board", "Product Studio"],
    "White": ["Blank Canvas", "Product Page", "Gallery Wall", "Launch Deck"],
}


def _choose(items: list[str], seed: str, salt: str) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).digest()
    return items[int.from_bytes(digest[:4], "big") % len(items)]


def candidate_labels(candidate: Candidate, target_date: date) -> tuple[str, str, str]:
    lightness, chroma, _ = candidate.oklch
    family = color_family_name(candidate.oklab)
    seed = f"{target_date.isoformat()}:{candidate.hex}:{','.join(candidate.sectors)}"

    if family in NEUTRAL_OBJECTS:
        noun = _choose(NEUTRAL_OBJECTS[family], seed, "noun")
        if family in {"Black", "Charcoal"}:
            qualifier = _choose(QUALIFIERS_DARK, seed, "qualifier")
        elif family in {"White", "Light Gray"}:
            qualifier = _choose(QUALIFIERS_LIGHT, seed, "qualifier")
        else:
            qualifier = _choose(QUALIFIERS_MUTED, seed, "qualifier")
        creative = noun if qualifier.lower() in noun.lower() else f"{qualifier} {noun}"
        return family, creative, f"{creative} {family}"

    items = OBJECTS.get(family, ["Commercial Signal", "Campaign Color", "Launch Creative"])
    noun = _choose(items, seed, "noun")
    if lightness < 0.38:
        qualifier = _choose(QUALIFIERS_DARK, seed, "qualifier")
    elif lightness > 0.82:
        qualifier = _choose(QUALIFIERS_LIGHT, seed, "qualifier")
    elif chroma < 0.065:
        qualifier = _choose(QUALIFIERS_MUTED, seed, "qualifier")
    elif chroma > 0.17:
        qualifier = _choose(QUALIFIERS_VIVID, seed, "qualifier")
    else:
        qualifier = ""
    creative = noun if not qualifier or qualifier.lower() in noun.lower() else f"{qualifier} {noun}"
    display = f"{creative} {family}"
    return family, creative, display


def name_candidate(candidate: Candidate, target_date: date) -> str:
    return candidate_labels(candidate, target_date)[2]


def family_label_for_candidate(candidate: Candidate) -> str:
    """Return the deterministic, technically grounded color-family label."""
    return color_family_name(candidate.oklab)
