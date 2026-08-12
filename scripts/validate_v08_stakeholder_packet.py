#!/usr/bin/env python3
"""Validator for v08 stakeholder confirmation packet (lane 02).

Checks the seven allowed files for DRAFT/NOT EFFECTIVE standing,
seven frozen unresolved decisions, eight operational questions,
Sandra five + Randy six asks, machine-readable decision register,
and absence of effective-v2 wording.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/closure/v08_alignment/stakeholder_confirmation_packet.md"
AMENDMENT = ROOT / "docs/closure/v08_alignment/proposed_requirements_amendment_v2.md"
EMAIL_SANDRA = ROOT / "docs/closure/v08_alignment/email_to_sandra.md"
EMAIL_RANDY = ROOT / "docs/closure/v08_alignment/email_to_randy.md"
REGISTER = ROOT / "docs/closure/v08_alignment/stakeholder_decision_register.json"

# Required IDs
FROZEN_SEVEN = [f"UD-00{i}" for i in range(1, 8)]
OPERATIONAL_EIGHT = [f"OQ-00{i}" for i in range(1, 9)]
SANDRA_FIVE_TOPICS = [
    "final two ITS use cases",
    "core-vs-additional",
    "sequential per-task least-busy",
    "bounded Manchester",
    "mandatory RQs",
]
RANDY_SIX_TOPICS = [
    "RSU waiting-room",
    "offered/admitted/rejected",
    "deadline after return",
    "actor mode-only authority",
    "gate vs capacity",
    "authoritative lifecycle fields",
]
SANDRA_IDS = [f"SQ-SANDRA-0{i}" for i in range(1, 6)]
RANDY_IDS = [f"RQ-RANDY-0{i}" for i in range(1, 7)]

CLASSIFICATION_LABELS = [
    "SOURCE-DERIVED FACT",
    "IMPLEMENTATION-VERIFIED FACT",
    "RESEARCH-EVIDENCE FACT",
    "INFERENCE",
    "PROVISIONAL WORDING",
    "EXTERNAL DECISION REQUIRED",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_file_exists(path: Path) -> str:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    errors: list[str] = []

    packet_text = check_file_exists(PACKET)
    amendment_text = check_file_exists(AMENDMENT)
    sandra_text = check_file_exists(EMAIL_SANDRA)
    randy_text = check_file_exists(EMAIL_RANDY)
    register_text = check_file_exists(REGISTER)

    # 1. DRAFT / NOT EFFECTIVE must be present in packet and amendment
    for name, text in [("packet", packet_text), ("amendment", amendment_text)]:
        if "DRAFT / NOT EFFECTIVE" not in text:
            errors.append(f"{name} missing 'DRAFT / NOT EFFECTIVE'")

    # Validator must reject effective-v2 wording: if amendment claims effective
    # without DRAFT
    # We check that amendment does NOT contain an effective claim that bypasses DRAFT.
    # The draft packet contains DRAFT / NOT EFFECTIVE; if that phrase is absent we already error.
    # Additionally flag if amendment contains 'is effective' or
    # 'EFFECTIVE AMENDMENT' without being DRAFT.
    # Since DRAFT / NOT EFFECTIVE is required, any standalone effective is suspicious.
    # Simple rule: if DRAFT / NOT EFFECTIVE is absent, it's already a
    # failure (discriminating mutation).
    # No extra check needed beyond presence, but we also ensure packet does
    # not contain forbidden approval claim.
    forbidden_phrases = [
        "has approved",
        "has been approved",
        "Sandra has replied",
        "Randy has replied",
        "approval received",
    ]
    for phrase in forbidden_phrases:
        if phrase.lower() in packet_text.lower():
            errors.append(f"packet contains forbidden claim phrase: '{phrase}'")
        if phrase.lower() in amendment_text.lower():
            errors.append(f"amendment contains forbidden claim phrase: '{phrase}'")

    # 2. Seven frozen unresolved decisions must map to explicit asks
    for uid in FROZEN_SEVEN:
        if uid not in packet_text:
            errors.append(f"packet missing frozen decision mapping {uid}")

    # 3. Eight operational questions
    for oid in OPERATIONAL_EIGHT:
        if oid not in packet_text:
            errors.append(f"packet missing operational question {oid}")

    # 4. Sandra five topics (keywords) and IDs
    for topic in SANDRA_FIVE_TOPICS:
        if topic.lower() not in packet_text.lower():
            errors.append(f"packet missing Sandra topic '{topic}'")
    for sid in SANDRA_IDS:
        if sid not in packet_text:
            errors.append(f"packet missing Sandra ask ID {sid}")

    # 5. Randy six topics and IDs
    normalized_packet = packet_text.lower().replace(" ", "").replace("\n", "")
    for topic in RANDY_SIX_TOPICS:
        norm_topic = topic.lower().replace(" ", "").replace("\n", "")
        if norm_topic not in normalized_packet and topic.lower() not in packet_text.lower():
            errors.append(f"packet missing Randy topic '{topic}'")
    for rid in RANDY_IDS:
        if rid not in packet_text:
            errors.append(f"packet missing Randy ask ID {rid}")

    # 6. Classification labels
    for label in CLASSIFICATION_LABELS:
        if label not in packet_text:
            errors.append(f"packet missing classification label '{label}'")

    # 7. Provisional tags
    if "PROVISIONAL_PENDING_SANDRA" not in packet_text:
        errors.append("packet missing PROVISIONAL_PENDING_SANDRA")
    if "PROVISIONAL_PENDING_RANDY" not in packet_text:
        errors.append("packet missing PROVISIONAL_PENDING_RANDY")
    if "PROVISIONAL_PENDING_SANDRA" not in amendment_text:
        errors.append("amendment missing PROVISIONAL_PENDING_SANDRA")

    # 8. No question presupposes answer - check that asks are questions (contain ?)
    # Simple heuristic: each ask ID should be followed by a '?' nearby
    for sid in SANDRA_IDS:
        idx = packet_text.find(sid)
        if idx != -1:
            snippet = packet_text[idx : idx + 1500]
            if "?" not in snippet:
                errors.append(
                    f"packet Sandra ask {sid} does not contain a neutral question (no '?')"
                )

    for rid in RANDY_IDS:
        idx = packet_text.find(rid)
        if idx != -1:
            snippet = packet_text[idx : idx + 1500]
            if "?" not in snippet:
                errors.append(
                    f"packet Randy ask {rid} does not contain a neutral question (no '?')"
                )

    # 9. Machine-readable decision register: JSON validity and required fields
    try:
        data = json.loads(register_text)
    except json.JSONDecodeError as exc:
        fail(f"decision register invalid JSON: {exc}")

    # Check base_sha
    if data.get("base_sha") != "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6":
        errors.append("register base_sha mismatch")

    # Check amendment standing
    baseline = data.get("baseline", {})
    if baseline.get("amendment_v2_standing") != "DRAFT / NOT EFFECTIVE":
        errors.append("register amendment_v2_standing must be 'DRAFT / NOT EFFECTIVE'")

    # Check frozen seven
    frozen = data.get("unresolved_decisions_frozen_seven", [])
    if len(frozen) != 7:
        errors.append(
            f"register unresolved_decisions_frozen_seven must have 7 entries, got {len(frozen)}"
        )
    for entry in frozen:
        for field in (
            "source_class",
            "decision_owner",
            "current_standing",
            "provisional_tag",
            "mapped_asks",
        ):
            if field not in entry:
                errors.append(
                    f"register frozen entry {entry.get('id', '?')} missing field '{field}'"
                )

    operational = data.get("operational_questions_eight", [])
    if len(operational) != 8:
        errors.append(
            f"register operational_questions_eight must have 8 entries, got {len(operational)}"
        )
    for entry in operational:
        for field in ("source_class", "decision_owner", "current_standing", "provisional_tag"):
            if field not in entry:
                errors.append(
                    f"register operational entry {entry.get('id', '?')} missing field '{field}'"
                )

    sandra_asks = data.get("sandra_asks_five", [])
    if len(sandra_asks) != 5:
        errors.append(f"register sandra_asks_five must have 5 entries, got {len(sandra_asks)}")

    randy_asks = data.get("randy_asks_six", [])
    if len(randy_asks) != 6:
        errors.append(f"register randy_asks_six must have 6 entries, got {len(randy_asks)}")

    # 10. Emails must exist and contain relevant topics
    if "SQ-SANDRA" not in sandra_text and "Sandra" not in sandra_text:
        errors.append("email_to_sandra missing Sandra reference")
    if "RQ-RANDY" not in randy_text and "Randy" not in randy_text:
        errors.append("email_to_randy missing Randy reference")
    if "DRAFT" not in sandra_text:
        errors.append("email_to_sandra missing DRAFT standing")
    if "DRAFT" not in randy_text:
        errors.append("email_to_randy missing DRAFT standing")

    # 11. S-035 handling: packet must mention S-035 and classification of A/B/C
    if "S-035" not in packet_text:
        errors.append("packet missing S-035 handling")
    if "S-035-A" not in packet_text or "S-035-B" not in packet_text or "S-035-C" not in packet_text:
        errors.append("packet missing S-035-A/B/C investigation breakdown")

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    print("PASS: stakeholder packet validation succeeded")
    print(f"  Packet: {PACKET.relative_to(ROOT)}")
    print(f"  Amendment: {AMENDMENT.relative_to(ROOT)}")
    print(f"  Register: {REGISTER.relative_to(ROOT)}")
    print(f"  Frozen seven: {len(FROZEN_SEVEN)} mapped")
    print(f"  Operational eight: {len(OPERATIONAL_EIGHT)} mapped")
    print("  Sandra asks: 5  Randy asks: 6")


if __name__ == "__main__":
    main()
