"""Read-only Eclipse SUMO XML parsing and bounded canonicalisation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from pydantic import ValidationError

from traffictwin.canonical.records import TripRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.integration.sumo.models import (
    SumoResultManifest,
    SumoSummaryStep,
    SumoTripObservation,
    SumoTripStatus,
)
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding
from traffictwin.validation.report import ValidationReport

TRIPINFO_ATTRIBUTES = {
    "id",
    "depart",
    "departLane",
    "departPos",
    "departPosLat",
    "departSpeed",
    "departDelay",
    "arrival",
    "arrivalLane",
    "arrivalPos",
    "arrivalPosLat",
    "arrivalSpeed",
    "duration",
    "routeLength",
    "waitingTime",
    "waitingCount",
    "stopTime",
    "timeLoss",
    "rerouteNo",
    "devices",
    "vType",
    "speedFactor",
    "vaporized",
}
SUMMARY_ATTRIBUTES = {
    "time",
    "loaded",
    "inserted",
    "running",
    "waiting",
    "ended",
    "arrived",
    "collisions",
    "teleports",
    "halting",
    "stopped",
    "discarded",
    "meanWaitingTime",
    "meanTravelTime",
    "meanSpeed",
    "meanSpeedRelative",
    "duration",
}


@dataclass(frozen=True)
class SumoAdapterOutput:
    """Canonical and source-specific records produced by the XML adapter."""

    canonical: CanonicalTables
    trip_observations: list[SumoTripObservation]
    summary_steps: list[SumoSummaryStep]


class SumoResultsAdapter:
    """Parse declared SUMO result XML without launching or mutating SUMO."""

    def canonicalise(
        self,
        root: Path,
        manifest: SumoResultManifest,
        report: ValidationReport,
    ) -> SumoAdapterOutput:
        """Parse supported files and return deterministic typed records."""

        trip_path = root / manifest.files.tripinfo.path
        summary_path = root / manifest.files.summary.path
        trips, observations = self._parse_tripinfo(trip_path, manifest.files.tripinfo.path, report)
        summary_steps = self._parse_summary(summary_path, manifest.files.summary.path, report)
        return SumoAdapterOutput(
            canonical=CanonicalTables(trips=trips),
            trip_observations=observations,
            summary_steps=summary_steps,
        )

    def _parse_tripinfo(
        self,
        path: Path,
        source_file: str,
        report: ValidationReport,
    ) -> tuple[list[TripRecord], list[SumoTripObservation]]:
        root = _parse_xml(path, source_file, "tripinfos", report)
        if root is None:
            return [], []
        report.files_inspected.append(source_file)
        elements = [element for element in root if _local_name(element.tag) == "tripinfo"]
        ignored_elements = sorted(
            {
                _local_name(element.tag)
                for element in root
                if _local_name(element.tag) not in {"metadata", "tripinfo"}
            }
        )
        if ignored_elements:
            report.add(
                _finding(
                    ValidationCode.SUMO_XML_ELEMENT_IGNORED,
                    Severity.WARNING,
                    "unsupported tripinfo elements remain raw and were not canonicalised: "
                    + ", ".join(ignored_elements),
                    file=source_file,
                    may_continue=True,
                    affected_capabilities=["sumo_person_container_import"],
                )
            )
        unknown_attributes = sorted(
            {attribute for element in elements for attribute in element.attrib}
            - TRIPINFO_ATTRIBUTES
        )
        if unknown_attributes:
            report.add(
                _finding(
                    ValidationCode.SUMO_XML_ATTRIBUTE_IGNORED,
                    Severity.WARNING,
                    "unmapped tripinfo attributes remain raw: " + ", ".join(unknown_attributes),
                    file=source_file,
                    may_continue=True,
                )
            )

        canonical: list[TripRecord] = []
        observations: list[SumoTripObservation] = []
        identifiers: set[str] = set()
        incomplete_count = 0
        undeparted_count = 0
        for source_record, element in enumerate(elements, start=1):
            identifier = element.attrib.get("id", "").strip()
            if not identifier:
                report.add(
                    _finding(
                        ValidationCode.SUMO_XML_REQUIRED_ATTRIBUTE_MISSING,
                        Severity.ERROR,
                        "tripinfo id is required",
                        file=source_file,
                        row=source_record,
                        field="id",
                        may_continue=False,
                    )
                )
                continue
            if identifier in identifiers:
                report.add(
                    _finding(
                        ValidationCode.SUMO_TRIP_ID_DUPLICATE,
                        Severity.ERROR,
                        f"duplicate tripinfo vehicle id: {identifier}",
                        file=source_file,
                        row=source_record,
                        field="id",
                        value=identifier,
                        may_continue=False,
                    )
                )
                continue
            identifiers.add(identifier)
            depart = _required_float(element, "depart", source_file, source_record, report)
            arrival = _required_float(element, "arrival", source_file, source_record, report)
            duration = _required_float(element, "duration", source_file, source_record, report)
            if depart is None or arrival is None or duration is None:
                continue
            if duration < 0:
                report.add(
                    _finding(
                        ValidationCode.SUMO_XML_VALUE_INVALID,
                        Severity.ERROR,
                        "tripinfo duration must be non-negative",
                        file=source_file,
                        row=source_record,
                        field="duration",
                        value=duration,
                        may_continue=False,
                    )
                )
                continue
            vaporized = element.attrib.get("vaporized", "").strip() or None
            if depart < 0:
                status = SumoTripStatus.UNDEPARTED
                undeparted_count += 1
            elif arrival < 0 or vaporized is not None:
                status = SumoTripStatus.INCOMPLETE
                incomplete_count += 1
            else:
                status = SumoTripStatus.COMPLETED
            observations.append(
                SumoTripObservation(
                    source_file=source_file,
                    source_record=source_record,
                    vehicle_id=identifier,
                    departure_time_s=depart if depart >= 0 else None,
                    reported_arrival_time_s=arrival if arrival >= 0 else None,
                    reported_duration_s=duration,
                    vaporized_reason=vaporized,
                    status=status,
                )
            )
            if status is SumoTripStatus.UNDEPARTED:
                continue
            if status is SumoTripStatus.COMPLETED:
                expected_duration = arrival - depart
                if abs(duration - expected_duration) > 1e-6:
                    report.add(
                        _finding(
                            ValidationCode.TRIP_DURATION_INCONSISTENT,
                            Severity.ERROR,
                            "SUMO trip duration does not equal arrival minus departure",
                            file=source_file,
                            row=source_record,
                            field="duration",
                            value=duration,
                            may_continue=False,
                            affected_capabilities=["journey_time_metrics"],
                        )
                    )
                    continue
                arrival_value: float | None = arrival
                duration_value: float | None = duration
            else:
                arrival_value = None
                duration_value = None
            canonical.append(
                TripRecord(
                    source_file=source_file,
                    source_row=source_record,
                    trip_id=identifier,
                    vehicle_id=identifier,
                    departure_time_s=depart,
                    arrival_time_s=arrival_value,
                    duration_s=duration_value,
                    route_id=None,
                )
            )
        if incomplete_count:
            report.add(
                _finding(
                    ValidationCode.SUMO_TRIPINFO_INCOMPLETE,
                    Severity.WARNING,
                    f"{incomplete_count} departed tripinfo records are incomplete; their "
                    "reported elapsed durations remain source-only",
                    file=source_file,
                    value=incomplete_count,
                    may_continue=True,
                    affected_capabilities=["journey_time_metrics"],
                )
            )
        if undeparted_count:
            report.add(
                _finding(
                    ValidationCode.SUMO_TRIPINFO_UNDEPARTED,
                    Severity.WARNING,
                    f"{undeparted_count} tripinfo records never departed and have no canonical "
                    "departure timestamp",
                    file=source_file,
                    value=undeparted_count,
                    may_continue=True,
                    affected_capabilities=["journey_time_metrics"],
                )
            )
        report.add(
            _finding(
                ValidationCode.SUMO_TRIPINFO_CANONICALISED,
                Severity.INFO,
                f"canonicalised {len(canonical)} of {len(observations)} valid tripinfo records",
                file=source_file,
                value=len(canonical),
                may_continue=True,
                affected_capabilities=["journey_time_metrics"],
            )
        )
        return canonical, observations

    def _parse_summary(
        self,
        path: Path,
        source_file: str,
        report: ValidationReport,
    ) -> list[SumoSummaryStep]:
        root = _parse_xml(path, source_file, "summary", report)
        if root is None:
            return []
        report.files_inspected.append(source_file)
        elements = [element for element in root if _local_name(element.tag) == "step"]
        ignored_elements = sorted(
            {
                _local_name(element.tag)
                for element in root
                if _local_name(element.tag) not in {"metadata", "step"}
            }
        )
        if ignored_elements:
            report.add(
                _finding(
                    ValidationCode.SUMO_XML_ELEMENT_IGNORED,
                    Severity.WARNING,
                    "unmapped summary elements remain raw: " + ", ".join(ignored_elements),
                    file=source_file,
                    may_continue=True,
                )
            )
        unknown_attributes = sorted(
            {attribute for element in elements for attribute in element.attrib} - SUMMARY_ATTRIBUTES
        )
        if unknown_attributes:
            report.add(
                _finding(
                    ValidationCode.SUMO_XML_ATTRIBUTE_IGNORED,
                    Severity.WARNING,
                    "unmapped summary attributes remain raw: " + ", ".join(unknown_attributes),
                    file=source_file,
                    may_continue=True,
                )
            )

        records: list[SumoSummaryStep] = []
        previous_time: float | None = None
        for source_record, element in enumerate(elements, start=1):
            time_s = _required_float(element, "time", source_file, source_record, report)
            running = _required_int(element, "running", source_file, source_record, report)
            if time_s is None or running is None:
                continue
            if time_s < 0 or running < 0:
                report.add(
                    _finding(
                        ValidationCode.SUMO_XML_VALUE_INVALID,
                        Severity.ERROR,
                        "summary time and running count must be non-negative",
                        file=source_file,
                        row=source_record,
                        may_continue=False,
                    )
                )
                continue
            if previous_time is not None and time_s <= previous_time:
                report.add(
                    _finding(
                        ValidationCode.SUMO_SUMMARY_TIME_ORDER_INVALID,
                        Severity.ERROR,
                        "summary step times must be strictly increasing",
                        file=source_file,
                        row=source_record,
                        field="time",
                        value=time_s,
                        may_continue=False,
                    )
                )
            previous_time = time_s
            try:
                records.append(
                    SumoSummaryStep(
                        source_file=source_file,
                        source_record=source_record,
                        time_s=time_s,
                        loaded=_optional_int(element, "loaded"),
                        inserted=_optional_int(element, "inserted"),
                        running=running,
                        waiting=_optional_int(element, "waiting"),
                        ended=_optional_int(element, "ended"),
                        arrived=_optional_int(element, "arrived"),
                        collisions=_optional_int(element, "collisions"),
                        teleports=_optional_int(element, "teleports"),
                        halting=_optional_int(element, "halting"),
                        stopped=_optional_int(element, "stopped"),
                        discarded=_optional_int(element, "discarded"),
                        mean_waiting_time_s=_optional_non_negative_float(
                            element, "meanWaitingTime"
                        ),
                        mean_travel_time_s=_optional_non_negative_float(element, "meanTravelTime"),
                        mean_speed_mps=_optional_non_negative_float(element, "meanSpeed"),
                        mean_speed_relative=_optional_non_negative_float(
                            element, "meanSpeedRelative"
                        ),
                        step_duration_ms=_optional_non_negative_float(element, "duration"),
                    )
                )
            except (ValueError, ValidationError) as exc:
                report.add(
                    _finding(
                        ValidationCode.SUMO_XML_VALUE_INVALID,
                        Severity.ERROR,
                        f"invalid summary step: {exc}",
                        file=source_file,
                        row=source_record,
                        may_continue=False,
                    )
                )
        report.add(
            _finding(
                ValidationCode.SUMO_SUMMARY_SOURCE_ONLY,
                Severity.INFO,
                f"parsed {len(records)} SUMO summary steps as source-specific evidence; no "
                "canonical traffic count mapping was inferred",
                file=source_file,
                value=len(records),
                may_continue=True,
                affected_capabilities=["sumo_summary_replay"],
            )
        )
        return records


def _parse_xml(
    path: Path,
    source_file: str,
    expected_root: str,
    report: ValidationReport,
) -> ElementTree.Element[str] | None:
    try:
        if _contains_unsafe_xml_declaration(path):
            report.add(
                _finding(
                    ValidationCode.SUMO_XML_UNSAFE,
                    Severity.FATAL,
                    "DTD and entity declarations are not accepted in SUMO result XML",
                    file=source_file,
                    may_continue=False,
                )
            )
            return None
        root = ElementTree.parse(path).getroot()  # noqa: S314 - DTD/entity declarations rejected.
    except (OSError, ElementTree.ParseError) as exc:
        report.add(
            _finding(
                ValidationCode.SUMO_XML_MALFORMED,
                Severity.FATAL,
                f"could not parse SUMO XML: {exc}",
                file=source_file,
                may_continue=False,
            )
        )
        return None
    if _local_name(root.tag) != expected_root:
        report.add(
            _finding(
                ValidationCode.SUMO_XML_ROOT_INVALID,
                Severity.FATAL,
                f"expected <{expected_root}> root, found <{_local_name(root.tag)}>",
                file=source_file,
                may_continue=False,
            )
        )
        return None
    return root


def _contains_unsafe_xml_declaration(path: Path) -> bool:
    needles = (b"<!doctype", b"<!entity")
    carry = b""
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            content = (carry + chunk).lower()
            if any(needle in content for needle in needles):
                return True
            carry = content[-16:]
    return False


def _required_float(
    element: ElementTree.Element[str],
    attribute: str,
    source_file: str,
    source_record: int,
    report: ValidationReport,
) -> float | None:
    value = element.attrib.get(attribute)
    if value is None:
        report.add(
            _finding(
                ValidationCode.SUMO_XML_REQUIRED_ATTRIBUTE_MISSING,
                Severity.ERROR,
                f"required XML attribute is missing: {attribute}",
                file=source_file,
                row=source_record,
                field=attribute,
                may_continue=False,
            )
        )
        return None
    try:
        number = float(value)
    except ValueError:
        report.add(
            _finding(
                ValidationCode.SUMO_XML_VALUE_INVALID,
                Severity.ERROR,
                f"XML attribute must be numeric: {attribute}",
                file=source_file,
                row=source_record,
                field=attribute,
                value=value,
                may_continue=False,
            )
        )
        return None
    if not math.isfinite(number):
        report.add(
            _finding(
                ValidationCode.SUMO_XML_VALUE_INVALID,
                Severity.ERROR,
                f"XML attribute must be finite: {attribute}",
                file=source_file,
                row=source_record,
                field=attribute,
                value=value,
                may_continue=False,
            )
        )
        return None
    return number


def _required_int(
    element: ElementTree.Element[str],
    attribute: str,
    source_file: str,
    source_record: int,
    report: ValidationReport,
) -> int | None:
    value = element.attrib.get(attribute)
    if value is None:
        report.add(
            _finding(
                ValidationCode.SUMO_XML_REQUIRED_ATTRIBUTE_MISSING,
                Severity.ERROR,
                f"required XML attribute is missing: {attribute}",
                file=source_file,
                row=source_record,
                field=attribute,
                may_continue=False,
            )
        )
        return None
    try:
        return int(value)
    except ValueError:
        report.add(
            _finding(
                ValidationCode.SUMO_XML_VALUE_INVALID,
                Severity.ERROR,
                f"XML attribute must be an integer: {attribute}",
                file=source_file,
                row=source_record,
                field=attribute,
                value=value,
                may_continue=False,
            )
        )
        return None


def _optional_int(element: ElementTree.Element[str], attribute: str) -> int | None:
    value = element.attrib.get(attribute)
    return None if value is None else int(value)


def _optional_non_negative_float(element: ElementTree.Element[str], attribute: str) -> float | None:
    value = element.attrib.get(attribute)
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{attribute} must be finite")
    return None if number < 0 else number


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _finding(
    code: ValidationCode,
    severity: Severity,
    message: str,
    *,
    file: str | None = None,
    row: int | None = None,
    field: str | None = None,
    value: object = None,
    may_continue: bool,
    affected_capabilities: list[str] | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        file=file,
        row=row,
        field=field,
        value=value,
        may_continue=may_continue,
        affected_capabilities=affected_capabilities or [],
    )
