from __future__ import annotations

import gzip

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.archive import ArchivePolicy
from traffictwin.integration.manchester.xml import (
    ManchesterXmlError,
    XmlPolicy,
    parse_gzip_xml,
    parse_xml,
)

SIRI_NAMESPACE = "http://www.siri.org.uk/siri"


def _policy(**updates: object) -> XmlPolicy:
    values: dict[str, object] = {
        "max_input_bytes": 10_000,
        "max_elements": 10,
        "max_depth": 4,
        "max_attributes_per_element": 3,
        "max_text_characters": 100,
        "allowed_root_local_names": ("Siri",),
        "allowed_namespaces": (SIRI_NAMESPACE,),
    }
    values.update(updates)
    return XmlPolicy.model_validate(values)


def _archive_policy() -> ArchivePolicy:
    return ArchivePolicy(
        max_compressed_bytes=10_000,
        max_decompressed_bytes=10_000,
        max_member_bytes=10_000,
        max_members=1,
        max_compression_ratio=100.0,
        allowed_suffixes=(),
    )


def test_parse_namespaced_xml_records_runtime_and_resource_diagnostics() -> None:
    payload = (
        f'<Siri xmlns="{SIRI_NAMESPACE}"><ServiceDelivery id="one">'
        "<VehicleMonitoringDelivery>synthetic</VehicleMonitoringDelivery>"
        "</ServiceDelivery></Siri>"
    ).encode()
    result = parse_xml(payload, policy=_policy())
    assert result.root.tag == f"{{{SIRI_NAMESPACE}}}Siri"
    assert result.expat_version
    assert result.element_count == 3
    assert result.maximum_depth == 3
    assert result.text_characters == len("id") + len("one") + len("synthetic")


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE Siri [<!ENTITY x "expanded">]><Siri>&x;</Siri>',
        b'<!DOCTYPE Siri SYSTEM "https://evil.test/entity"><Siri/>',
        b"<Siri><broken></Siri>",
    ],
)
def test_parser_rejects_dtd_entities_external_references_and_malformed_xml(payload: bytes) -> None:
    with pytest.raises(ManchesterXmlError, match="forbidden constructs"):
        parse_xml(payload, policy=_policy(allowed_namespaces=()))


def test_parser_rejects_wrong_root_or_namespace() -> None:
    with pytest.raises(ManchesterXmlError, match="root element"):
        parse_xml(
            f'<Other xmlns="{SIRI_NAMESPACE}"/>'.encode(),
            policy=_policy(),
        )
    with pytest.raises(ManchesterXmlError, match="root namespace"):
        parse_xml(b'<Siri xmlns="https://unexpected.test"/>', policy=_policy())
    payload = f'<Siri xmlns="{SIRI_NAMESPACE}"><Other xmlns="https://unexpected.test"/></Siri>'
    with pytest.raises(ManchesterXmlError, match="element namespace"):
        parse_xml(payload.encode(), policy=_policy())


@pytest.mark.parametrize(
    ("payload", "updates", "message"),
    [
        (b"", {}, "empty"),
        (b"<Siri/>", {"max_input_bytes": 4}, "exceeds policy"),
        (b"<Siri><a/><b/></Siri>", {"allowed_namespaces": (), "max_elements": 2}, "element count"),
        (b"<Siri><a><b/></a></Siri>", {"allowed_namespaces": (), "max_depth": 2}, "depth"),
        (
            b'<Siri one="1" two="2"/>',
            {"allowed_namespaces": (), "max_attributes_per_element": 1},
            "attribute count",
        ),
        (
            b"<Siri>too much text</Siri>",
            {"allowed_namespaces": (), "max_text_characters": 3},
            "text size",
        ),
    ],
)
def test_parser_enforces_every_resource_bound(
    payload: bytes, updates: dict[str, object], message: str
) -> None:
    with pytest.raises(ManchesterXmlError, match=message):
        parse_xml(payload, policy=_policy(**updates))


def test_gzip_is_bounded_before_xml_parsing() -> None:
    payload = f'<Siri xmlns="{SIRI_NAMESPACE}"><ServiceDelivery/></Siri>'.encode()
    result = parse_gzip_xml(
        gzip.compress(payload),
        archive_policy=_archive_policy(),
        xml_policy=_policy(),
    )
    assert result.element_count == 2


def test_xml_policy_rejects_unknown_duplicate_and_empty_names() -> None:
    with pytest.raises(ValidationError):
        _policy(unknown=True)
    with pytest.raises(ValidationError, match="unique"):
        _policy(allowed_root_local_names=("Siri", "Siri"))
    with pytest.raises(ValidationError, match="non-empty"):
        _policy(allowed_root_local_names=("",))
