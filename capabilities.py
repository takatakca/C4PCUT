"""Explicit private workspace resource policy. Not commercial entitlement."""
import math
from dataclasses import dataclass
import engine
import projects

class CapabilityDenied(ValueError):
    pass

FEATURES=frozenset(("transcribe","ollama","clipper","music","animated_captions","studio_pack"))
FIELDS={"max_output_edge","max_render_seconds","max_projects","qualities","features"}

@dataclass(frozen=True)
class Policy:
    max_output_edge: int
    max_render_seconds: int
    max_projects: int
    qualities: frozenset
    features: frozenset

    def public(self):
        return {"max_output_edge":self.max_output_edge,"max_render_seconds":self.max_render_seconds,
                "max_projects":self.max_projects,"qualities":sorted(self.qualities),"features":sorted(self.features)}

    def require(self,feature):
        if feature not in self.features:
            raise CapabilityDenied("Feature unavailable in this workspace")

    def render(self,preset,framing,quality,duration,metadata,caption_mode,use_music):
        dims=engine.validate_format(preset,framing)
        engine.validate_quality(quality)
        # Original output is not an exemption from the resolution cap.
        edge=max(dims) if dims else max(metadata["width"],metadata["height"])
        if edge>self.max_output_edge or duration>self.max_render_seconds or quality not in self.qualities:
            raise CapabilityDenied("Export exceeds workspace capabilities")
        if caption_mode!="soft":
            self.require("animated_captions")
        if use_music:
            self.require("music")

def parse(value):
    if not isinstance(value,dict) or set(value)!=FIELDS:
        raise ValueError("Invalid workspace capability fields")
    edge,seconds,count=value["max_output_edge"],value["max_render_seconds"],value["max_projects"]
    if type(edge) is not int or edge not in (1280,1920,2560,3840,4096):
        raise ValueError("Invalid output edge")
    if type(seconds) is not int or not 1<=seconds<=engine.MAX_DURATION:
        raise ValueError("Invalid duration limit")
    if type(count) is not int or not 1<=count<=projects.MAX_PROJECTS:
        raise ValueError("Invalid project limit")
    def choices(items,allowed,empty=False):
        if not isinstance(items,list) or (not items and not empty) or any(not isinstance(x,str) or x not in allowed for x in items) or len(items)!=len(set(items)):
            raise ValueError("Invalid capability choices")
        return frozenset(items)
    return Policy(edge,seconds,count,choices(value["qualities"],engine.QUALITIES),choices(value["features"],FEATURES,True))
