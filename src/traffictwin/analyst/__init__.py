"""TrafficTwin Analyst: deterministic evidence packet, classification, prose.

Order is fixed by ADR-005: existing deterministic services produce the
facts; :func:`build_analyst_packet` restates them; :func:`classify_packet`
maps existing rule outcomes onto a bounded signal; optional LLM prose
rendering comes last and can never change any of it.
"""

from traffictwin.analyst.classify import classify_packet
from traffictwin.analyst.models import (
    SIGNAL_DISPLAY_NAMES,
    AnalystClassification,
    AnalystEvidencePacket,
    AnalystRefusalCode,
    AnalystRefusalError,
    AnalystSignal,
)
from traffictwin.analyst.packet import build_analyst_packet
from traffictwin.analyst.prose import (
    AnalystProse,
    AnalystProseError,
    AnalystProseRequest,
    analyst_prose_status,
    build_prose_request,
    render_analyst_prose,
)

__all__ = [
    "SIGNAL_DISPLAY_NAMES",
    "AnalystClassification",
    "AnalystEvidencePacket",
    "AnalystProse",
    "AnalystProseError",
    "AnalystProseRequest",
    "AnalystRefusalCode",
    "AnalystRefusalError",
    "AnalystSignal",
    "analyst_prose_status",
    "build_analyst_packet",
    "build_prose_request",
    "classify_packet",
    "render_analyst_prose",
]
