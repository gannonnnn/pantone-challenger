from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

from challenger.color import distance, warm_or_cool
from challenger.models import Observation, PaletteRegime


def calculate_regime(observations: list[Observation]) -> PaletteRegime:
    if not observations:
        return PaletteRegime(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "insufficient evidence", [])
    # Use one highest-confidence region per independent actor so image-heavy pages do not
    # receive more regime weight than sources with one strong creative region.
    best_by_source = {}
    for observation in observations:
        prior = best_by_source.get(observation.source_id)
        if prior is None or observation.region.confidence > prior.region.confidence:
            best_by_source[observation.source_id] = observation
    observations = list(best_by_source.values())

    neutral_values = []
    chroma_values = []
    lightness_values = []
    contrast_values = []
    palette_sizes = []
    monochrome = []
    warm = 0.0
    cool = 0.0
    muted = 0.0
    electric = 0.0
    pairs = defaultdict(float)
    for obs in observations:
        swatches = obs.swatches[:5]
        if not swatches:
            continue
        weights = [s.adjusted_share if s.adjusted_share is not None else s.share for s in swatches]
        total = sum(weights) or 1.0
        neutral_values.append(
            sum(weight for s, weight in zip(swatches, weights, strict=False) if s.is_neutral) / total
        )
        chroma_values.extend(
            s.oklch[1]
            for s, weight in zip(swatches, weights, strict=False)
            for _ in range(max(1, int(weight * 10)))
        )
        lightness_values.extend(
            s.oklch[0]
            for s, weight in zip(swatches, weights, strict=False)
            for _ in range(max(1, int(weight * 10)))
        )
        palette_sizes.append(len(swatches))
        nonneutral = [s for s in swatches if not s.is_neutral]
        if nonneutral:
            hues = [s.oklch[2] for s in nonneutral]
            for s in nonneutral:
                weight = s.adjusted_share if s.adjusted_share is not None else s.share
                if warm_or_cool(s.oklch[2]) == "warm":
                    warm += weight
                else:
                    cool += weight
                muted += weight if s.oklch[1] < 0.10 else 0
                electric += weight if s.oklch[1] >= 0.18 else 0
            monochrome.append(1.0 if max(hues) - min(hues) < 25 else 0.0)
        else:
            monochrome.append(1.0)
        if len(swatches) >= 2:
            contrast_values.append(max(distance(a.oklab, b.oklab) for a, b in combinations(swatches, 2)))
        for a, b in combinations(nonneutral[:4], 2):
            key = tuple(sorted((a.hex, b.hex)))
            a_weight = a.adjusted_share if a.adjusted_share is not None else a.share
            b_weight = b.adjusted_share if b.adjusted_share is not None else b.share
            pairs[key] += min(a_weight, b_weight) * obs.region.confidence
    neutral_share = float(np.mean(neutral_values)) if neutral_values else 0.0
    median_chroma = float(np.median(chroma_values)) if chroma_values else 0.0
    mean_lightness = float(np.mean(lightness_values)) if lightness_values else 0.0
    total_temp = warm + cool or 1.0
    muted_total = muted + electric or 1.0
    dominant = _regime_label(neutral_share, median_chroma, float(np.mean(contrast_values)) if contrast_values else 0.0)
    top_pairs = [
        {"colors": list(colors), "score": round(score, 4)}
        for colors, score in sorted(pairs.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    return PaletteRegime(
        neutral_share=round(neutral_share, 4),
        median_chroma=round(median_chroma, 4),
        mean_lightness=round(mean_lightness, 4),
        warm_share=round(warm / total_temp, 4),
        cool_share=round(cool / total_temp, 4),
        mean_contrast=round(float(np.mean(contrast_values)) if contrast_values else 0.0, 4),
        mean_palette_size=round(float(np.mean(palette_sizes)) if palette_sizes else 0.0, 2),
        monochrome_share=round(float(np.mean(monochrome)) if monochrome else 0.0, 4),
        muted_share=round(muted / muted_total, 4),
        electric_share=round(electric / muted_total, 4),
        dominant_regime=dominant,
        top_pairs=top_pairs,
    )


def _regime_label(neutral_share: float, chroma: float, contrast: float) -> str:
    if neutral_share >= 0.68 and chroma < 0.06:
        return "neutral minimalism"
    if chroma < 0.075 and contrast < 0.20:
        return "soft muted palettes"
    if chroma < 0.11 and contrast < 0.28:
        return "pastel and softened color"
    if chroma >= 0.16 and contrast >= 0.30:
        return "high-chroma maximalism"
    if chroma >= 0.13:
        return "saturated accents"
    if contrast >= 0.32:
        return "high-contrast mixed palettes"
    return "grounded mid-chroma color"


def select_palette_pair(regime: PaletteRegime, min_score: float = 0.20):
    if not regime.top_pairs:
        return None
    top = regime.top_pairs[0]
    if top["score"] < min_score:
        return None
    return top
