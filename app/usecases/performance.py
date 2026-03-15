"""
Performance Use Cases - Performance Point Calculation and Analysis

This module provides business logic for calculating performance points (PP)
and difficulty ratings for osu! gameplay scores. It implements the use case
pattern for performance calculations, providing a clean abstraction layer
between the API endpoints and the underlying PP calculation library.

The module handles performance calculations for all osu! game modes,
supporting both accuracy-based and hit-count-based score evaluation.
It integrates with the akatsuki_pp_py library for accurate PP calculations
and provides structured results for performance and difficulty analysis.

Key Features:
    - Performance point calculation for all game modes
    - Difficulty rating analysis with multiple metrics
    - Support for both accuracy and hit-count based evaluation
    - Mod combination handling (including Nightcore to DoubleTime conversion)
    - Batch processing for mass recalculation scenarios
    - Error handling for invalid beatmap files
    - Structured result formatting for API responses

Integration Points:
    - Score submission in app/api/domains/osu.py
    - Leaderboard generation in app/api/v2/players.py
    - Beatmap difficulty analysis in app/api/v2/maps.py
    - Performance tracking in app/repositories/scores.py
    - Achievement validation in app/usecases/achievements.py

Performance Calculation:
    - Uses akatsuki_pp_py library for accurate PP calculations
    - Supports all osu! game modes (osu!, taiko, catch, mania)
    - Handles mod combinations and their effects on PP
    - Calculates both performance and difficulty ratings
    - Provides detailed breakdown of PP components

Difficulty Analysis:
    - Star rating calculation for beatmaps
    - Component breakdown (aim, speed, flashlight, etc.)
    - Mode-specific difficulty metrics
    - Slider factor and rhythm analysis
    - Peak difficulty assessment

Usage Pattern:
    # Calculate performance for a single score
    results = calculate_performances(
        osu_file_path="path/to/beatmap.osu",
        scores=[score_params]
    )
    
    # Access performance data
    for result in results:
        pp = result["performance"]["pp"]
        stars = result["difficulty"]["stars"]
        
    # Batch calculate for multiple scores
    results = calculate_performances(
        osu_file_path="path/to/beatmap.osu",
        scores=[score1, score2, score3]
    )

Related Files:
    - app/objects/score.py: Score data model
    - app/api/domains/osu.py: Score submission handling
    - app/api/v2/players.py: Leaderboard generation
    - app/repositories/scores.py: Score database operations
    - app/constants/mods.py: Mod definitions and handling
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypedDict

from akatsuki_pp_py import Beatmap
from akatsuki_pp_py import Calculator

from app.constants.mods import Mods


@dataclass
class ScoreParams:
    mode: int
    mods: int | None = None
    combo: int | None = None

    # caller may pass either acc OR 300/100/50/geki/katu/miss
    # passing both will result in a value error being raised
    acc: float | None = None

    n300: int | None = None
    n100: int | None = None
    n50: int | None = None
    ngeki: int | None = None
    nkatu: int | None = None
    nmiss: int | None = None


class PerformanceRating(TypedDict):
    pp: float
    pp_acc: float | None
    pp_aim: float | None
    pp_speed: float | None
    pp_flashlight: float | None
    effective_miss_count: float | None
    pp_difficulty: float | None


class DifficultyRating(TypedDict):
    stars: float
    aim: float | None
    speed: float | None
    flashlight: float | None
    slider_factor: float | None
    speed_note_count: float | None
    stamina: float | None
    color: float | None
    rhythm: float | None
    peak: float | None


class PerformanceResult(TypedDict):
    performance: PerformanceRating
    difficulty: DifficultyRating


def calculate_performances(
    osu_file_path: str,
    scores: Iterable[ScoreParams],
) -> list[PerformanceResult]:
    """\
    Calculate performance for multiple scores on a single beatmap.

    Typically most useful for mass-recalculation situations.

    TODO: Some level of error handling & returning to caller should be
    implemented here to handle cases where e.g. the beatmap file is invalid
    or there an issue during calculation.
    """
    calc_bmap = Beatmap(path=osu_file_path)

    results: list[PerformanceResult] = []

    for score in scores:
        if score.acc and (
            score.n300 or score.n100 or score.n50 or score.ngeki or score.nkatu
        ):
            raise ValueError(
                "Must not specify accuracy AND 300/100/50/geki/katu. Only one or the other.",
            )

        # rosupp ignores NC and requires DT
        if score.mods is not None:
            if score.mods & Mods.NIGHTCORE:
                score.mods |= Mods.DOUBLETIME

        calculator = Calculator(
            mode=score.mode,
            mods=score.mods or 0,
            combo=score.combo,
            acc=score.acc,
            n300=score.n300,
            n100=score.n100,
            n50=score.n50,
            n_geki=score.ngeki,
            n_katu=score.nkatu,
            n_misses=score.nmiss,
        )
        result = calculator.performance(calc_bmap)

        pp = result.pp

        if math.isnan(pp) or math.isinf(pp):
            # TODO: report to logserver
            pp = 0.0
        else:
            pp = round(pp, 3)

        results.append(
            {
                "performance": {
                    "pp": pp,
                    "pp_acc": result.pp_acc,
                    "pp_aim": result.pp_aim,
                    "pp_speed": result.pp_speed,
                    "pp_flashlight": result.pp_flashlight,
                    "effective_miss_count": result.effective_miss_count,
                    "pp_difficulty": result.pp_difficulty,
                },
                "difficulty": {
                    "stars": result.difficulty.stars,
                    "aim": result.difficulty.aim,
                    "speed": result.difficulty.speed,
                    "flashlight": result.difficulty.flashlight,
                    "slider_factor": result.difficulty.slider_factor,
                    "speed_note_count": result.difficulty.speed_note_count,
                    "stamina": result.difficulty.stamina,
                    "color": result.difficulty.color,
                    "rhythm": result.difficulty.rhythm,
                    "peak": result.difficulty.peak,
                },
            },
        )

    return results
