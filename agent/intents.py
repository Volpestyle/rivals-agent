"""Typed intents: what the brain asks the reflex controller (L4) to do.

The vocabulary is the typed primitives of docs/spiderman-kit.md. Each intent
names the primitives it may play; the controller does the aiming and timing.

  Idle, Search        no primitive: stand down / sweep the camera
  Engage(target)      web_cluster, melee_combo, uppercut: aim, close in, fight
  SwingTo(anchor)     swing_start(anchor) / web_zip(point)
  Pull(target)        pull       RB on an UNTAGGED enemy: they come TO YOU
  WebStrike(target)   web_strike RB on a TAGGED enemy:   YOU GO to them
  Combo(BURST, t)     burst(t)   web_cluster -> web_strike -> uppercut -> melee_combo -> web_cluster;
                                 tags first, so it ends with YOU AT the target
  Disengage           break line of sight and get away

Get Over Here! is one button whose meaning is set by the Spider-Tracer on the
target, so Pull and WebStrike are separate intents and never interchangeable.

Detections carry no track id (the detector does not give one), so an intent
holds the Detection as seen at decision time. The controller runs faster than
the brain and re-associates it with the nearest current detection each frame.
"""
from dataclasses import dataclass

from .state import Detection

BURST = "burst"  # the kit's one macro; Combo.name is always one of these
MACROS = (BURST,)


@dataclass(frozen=True)
class Idle:
    """Do nothing: perception is down or there is nothing worth doing."""


@dataclass(frozen=True)
class Search:
    """No hostile in view: sweep the camera / roam until one shows up."""


@dataclass(frozen=True)
class Engage:
    """Aim at the target, close in, and fight with web_cluster, melee_combo and uppercut."""
    target: Detection


@dataclass(frozen=True)
class SwingTo:
    anchor: Detection


@dataclass(frozen=True)
class Pull:
    """Get Over Here! on an untagged target: it is dragged to Spider-Man. Needs aim."""
    target: Detection


@dataclass(frozen=True)
class WebStrike:
    """Get Over Here! on a tagged target: Spider-Man is zipped to it. Auto-locks."""
    target: Detection


@dataclass(frozen=True)
class Combo:
    """A kit macro the controller plays start to finish; name is one of MACROS."""
    name: str
    target: Detection


@dataclass(frozen=True)
class Disengage:
    """Break line of sight and get away until told otherwise."""


Intent = Idle | Search | Engage | SwingTo | Pull | WebStrike | Combo | Disengage
