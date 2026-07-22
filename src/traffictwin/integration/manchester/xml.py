"""Hardened, resource-bounded XML parsing for Manchester source adapters."""

from __future__ import annotations

import pyexpat
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element, ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring
from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.integration.manchester.archive import ArchivePolicy, decompress_gzip


class ManchesterXmlError(ValueError):
    """Raised when untrusted XML violates syntax, security, or resource policy."""


class XmlPolicy(BaseModel):
    """Exact syntax and resource boundary for one XML source family."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_input_bytes: int = Field(gt=0, le=1_000_000_000)
    max_elements: int = Field(gt=0, le=5_000_000)
    max_depth: int = Field(gt=0, le=1_000)
    max_attributes_per_element: int = Field(ge=0, le=10_000)
    max_text_characters: int = Field(ge=0, le=1_000_000_000)
    allowed_root_local_names: tuple[str, ...]
    allowed_namespaces: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_names(self) -> XmlPolicy:
        """Require deterministic non-empty root and namespace allowlists."""

        if not self.allowed_root_local_names:
            raise ValueError("at least one allowed root local name is required")
        if any(not name or name.strip() != name for name in self.allowed_root_local_names):
            raise ValueError("root local names must be non-empty and trimmed")
        if len(set(self.allowed_root_local_names)) != len(self.allowed_root_local_names):
            raise ValueError("root local names must be unique")
        if any(not value or value.strip() != value for value in self.allowed_namespaces):
            raise ValueError("namespace values must be non-empty and trimmed")
        if len(set(self.allowed_namespaces)) != len(self.allowed_namespaces):
            raise ValueError("namespace values must be unique")
        return self


@dataclass(frozen=True, slots=True)
class ParsedXml:
    """A parsed tree accompanied by auditable parser/runtime diagnostics."""

    root: Element = field(repr=False)
    expat_version: str
    element_count: int
    maximum_depth: int
    text_characters: int


def parse_xml(payload: bytes, *, policy: XmlPolicy) -> ParsedXml:
    """Parse XML with DTD/entities/external references forbidden explicitly."""

    if not payload:
        raise ManchesterXmlError("XML payload is empty")
    if len(payload) > policy.max_input_bytes:
        raise ManchesterXmlError("XML payload exceeds policy")
    try:
        root = fromstring(
            payload,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, ParseError, ValueError) as exc:
        raise ManchesterXmlError(
            "XML payload is malformed or contains forbidden constructs"
        ) from exc

    root_namespace, root_name = _expanded_name(root.tag)
    if root_name not in policy.allowed_root_local_names:
        raise ManchesterXmlError("XML root element is not admitted")
    if policy.allowed_namespaces and root_namespace not in policy.allowed_namespaces:
        raise ManchesterXmlError("XML root namespace is not admitted")

    element_count = 0
    maximum_depth = 0
    text_characters = 0
    stack: list[tuple[Element, int]] = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        element_count += 1
        maximum_depth = max(maximum_depth, depth)
        if element_count > policy.max_elements:
            raise ManchesterXmlError("XML element count exceeds policy")
        if depth > policy.max_depth:
            raise ManchesterXmlError("XML depth exceeds policy")
        if len(element.attrib) > policy.max_attributes_per_element:
            raise ManchesterXmlError("XML attribute count exceeds policy")

        namespace, _ = _expanded_name(element.tag)
        if policy.allowed_namespaces and namespace not in policy.allowed_namespaces:
            raise ManchesterXmlError("XML element namespace is not admitted")
        for attribute_name in element.attrib:
            attribute_namespace, _ = _expanded_name(attribute_name)
            if (
                policy.allowed_namespaces
                and attribute_namespace is not None
                and attribute_namespace not in policy.allowed_namespaces
            ):
                raise ManchesterXmlError("XML attribute namespace is not admitted")

        text_characters += len(element.text or "") + len(element.tail or "")
        text_characters += sum(len(name) + len(value) for name, value in element.attrib.items())
        if text_characters > policy.max_text_characters:
            raise ManchesterXmlError("XML text size exceeds policy")
        stack.extend((child, depth + 1) for child in reversed(element))

    return ParsedXml(
        root=root,
        expat_version=pyexpat.EXPAT_VERSION,
        element_count=element_count,
        maximum_depth=maximum_depth,
        text_characters=text_characters,
    )


def parse_gzip_xml(
    payload: bytes,
    *,
    archive_policy: ArchivePolicy,
    xml_policy: XmlPolicy,
) -> ParsedXml:
    """Bound decompression before applying the hardened XML boundary."""

    xml_bytes = decompress_gzip(payload, policy=archive_policy)
    return parse_xml(xml_bytes, policy=xml_policy)


def _expanded_name(value: str) -> tuple[str | None, str]:
    if value.startswith("{") and "}" in value:
        namespace, local_name = value[1:].split("}", 1)
        if namespace and local_name:
            return namespace, local_name
    return None, value
