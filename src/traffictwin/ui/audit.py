"""Deterministic checks for browser-captured accessibility snapshots."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AccessibilitySnapshot(BaseModel):
    """Small semantic snapshot captured from a rendered application page."""

    model_config = ConfigDict(extra="forbid")

    page_name: str
    page_title: str
    main_h1_texts: list[str]
    unnamed_interactive_count: int = Field(ge=0)
    images_without_alt_count: int = Field(ge=0)
    duplicate_ids: list[str]
    horizontal_overflow: bool


class AccessibilityIssue(BaseModel):
    """One actionable, deterministic snapshot finding."""

    model_config = ConfigDict(extra="forbid")

    code: str
    page_name: str
    message: str


class AccessibilityAuditReport(BaseModel):
    """Basic accessibility audit; not a claim of WCAG conformance."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    snapshots: list[AccessibilitySnapshot]
    issues: list[AccessibilityIssue]
    passed: bool
    limitation: str = (
        "These automated semantic checks are a regression aid, not a WCAG conformance audit or "
        "a substitute for keyboard, screen-reader, contrast, and user testing."
    )

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


def analyse_accessibility_snapshots(
    snapshots: list[AccessibilitySnapshot],
) -> AccessibilityAuditReport:
    """Apply deterministic structural checks to browser-captured page snapshots."""

    issues: list[AccessibilityIssue] = []
    for snapshot in snapshots:
        if len(snapshot.main_h1_texts) != 1:
            issues.append(
                _issue(
                    "MAIN_HEADING_COUNT",
                    snapshot,
                    f"Expected one main h1; observed {len(snapshot.main_h1_texts)}.",
                )
            )
        if snapshot.unnamed_interactive_count:
            issues.append(
                _issue(
                    "UNNAMED_INTERACTIVE",
                    snapshot,
                    f"Observed {snapshot.unnamed_interactive_count} unnamed interactive elements.",
                )
            )
        if snapshot.images_without_alt_count:
            issues.append(
                _issue(
                    "IMAGE_ALT_MISSING",
                    snapshot,
                    f"Observed {snapshot.images_without_alt_count} images without alt attributes.",
                )
            )
        if snapshot.duplicate_ids:
            issues.append(
                _issue(
                    "DUPLICATE_DOM_ID",
                    snapshot,
                    "Duplicate DOM ids: " + ", ".join(snapshot.duplicate_ids),
                )
            )
        if snapshot.horizontal_overflow:
            issues.append(
                _issue(
                    "HORIZONTAL_OVERFLOW",
                    snapshot,
                    "The rendered document exceeds the viewport width.",
                )
            )
    return AccessibilityAuditReport(
        snapshots=snapshots,
        issues=issues,
        passed=not issues,
    )


def _issue(
    code: str,
    snapshot: AccessibilitySnapshot,
    message: str,
) -> AccessibilityIssue:
    return AccessibilityIssue(code=code, page_name=snapshot.page_name, message=message)
