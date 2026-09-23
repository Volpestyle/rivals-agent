"""The brain's KO debounce (brain._ko) against the HUD event extractor's own channel, on the same kill-feed reads (review of VUH-1315, F3).

Needs the perception group: `uv run --group perception pytest tests/test_options_extractor.py`.
"""
import pytest

from perception.events import DEBOUNCE, _Channel

from agent import brain
from agent.state import State
from tests.test_options import KO_CASES


@pytest.mark.parametrize("feeds, kos", KO_CASES)
def test_the_brain_confirms_a_ko_on_the_reads_the_event_extractor_does(feeds, kos):
    m, ch, brain_kos, extractor_kos = brain.Memory(), _Channel(DEBOUNCE["killfeed"]), [], []
    for i, feed in enumerate(feeds):
        if brain._ko(State(t=i / 10, frame=(1, 1), kill_feed=feed), m) is not None:
            brain_kos.append(i)
        moved = ch.push(i, i / 10, feed)
        if moved is not None and moved[1] is True:        # perception.events._kind: only the appearance is a ko_feed event
            extractor_kos.append(i)
    assert DEBOUNCE["killfeed"] == brain.FEED_CONFIRM
    assert brain_kos == extractor_kos == kos
