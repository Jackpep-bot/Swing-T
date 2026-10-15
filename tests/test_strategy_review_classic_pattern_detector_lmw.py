"""Review regression for classic_pattern_detector_lmw: the final kernel bandwidth is floored so noisy closes still
yield formation-scale extrema and the double-bottom branch can fire."""
import numpy as np

from swing_engine.core import registry

NAME = "classic_pattern_detector_lmw"


def test_noisy_25_bar_double_bottom_is_detected():
    # Bottoms at bars 6 and 31 (25 apart, card gap >= 22) with a wiggle on the middle rise, plus 0.4% daily noise.
    # Unfloored, CV picks h=1 and 0.3 x 1 = 0.3 bars echoes every noisy close reversal, so E1..E5 span ~8 bars.
    knots = [(0, 106), (6, 100), (12, 104), (15, 102), (20, 106), (31, 100), (37, 104)]
    base = np.interp(np.arange(38), *zip(*knots, strict=True))
    s = registry.get("strategy", NAME)(None)
    for seed in range(20):
        x = base * np.exp(np.random.default_rng(seed).normal(0, 0.004, 38))
        pat = s.detect(x)
        assert pat is not None and pat.kind == "double_bottom", seed
