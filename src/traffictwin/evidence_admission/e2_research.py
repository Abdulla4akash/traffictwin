"""Fail-closed source-bound admission for the built-in E2 research package.

Lane 04 — deterministic owner-authorized receipt binding strict artifact validation.

Standing is exactly ``OWNER-AUTHORIZED PRODUCT ADMISSION``; explicitly never
supervisor approved or Randy confirmed. ``ADMITTED_RESEARCH`` is available
only on exact match. Any mutation of evidence identity/value, fingerprint
or receipt field fails closed. Receipt is path-free, secret-free and
contains no scientific timestamp.

Public API:
  admit_e2_research(package: E2ResearchEvidencePackage)
    -> E2ResearchAdmissionReceipt
  load_admitted_builtin_e2_research()
    -> tuple[E2ResearchEvidencePackage, E2ResearchAdmissionReceipt]
Uses Lane 03 ``load_builtin_e2_research`` and strict validation; no fallback
package, no alternate schema, no path-based reads, no Any adapters.
"""

from __future__ import annotations

import hashlib
import json
import re
from importlib import resources
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.experiments.e2_research_artifact import load_builtin_e2_research
from traffictwin.experiments.e2_research_evidence import E2ResearchEvidencePackage

STANDING: Literal["OWNER-AUTHORIZED PRODUCT ADMISSION"] = "OWNER-AUTHORIZED PRODUCT ADMISSION"
ADMISSION_MODE: Literal["ADMITTED_RESEARCH"] = "ADMITTED_RESEARCH"
SCHEMA_VERSION: Literal["e2_research_admission_v1"] = "e2_research_admission_v1"

EXPECTED_PACKAGE_FINGERPRINT: str = (
    "195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269"
)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")

_PATH_SUBSTRINGS: tuple[str, ...] = (  # noqa: S108
    "/Users/",
    "/home/",
    "/tmp/",  # noqa: S108
    "C:\\",
)
_SECRET_SUBSTRINGS: tuple[str, ...] = (
    "secret",
    "credential",
    "api_key",
    "apikey",
    "password",
    "token",
)
_TIMESTAMP_KEYS: tuple[str, ...] = (
    "timestamp",
    "created_at",
    "updated_at",
    "admitted_at",
    "generated_at",
    "scientific_timestamp",
    "evaluation_time",
)


class E2ResearchAdmissionError(ValueError):
    """Fail-closed admission error — any mismatch or tampering raises this."""


def _canonical_fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _assert_no_paths_or_secrets(obj: object, label: str = "payload") -> None:
    def _walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                if any(pat in kl for pat in _SECRET_SUBSTRINGS):
                    if isinstance(v, bool):
                        continue
                    if isinstance(v, str) and v.strip() == "":
                        continue
                    if isinstance(v, str) and v.strip():
                        raise E2ResearchAdmissionError(
                            f"{label} contains forbidden secret pattern {kl!r}"
                        )
                for pat in _PATH_SUBSTRINGS:
                    if pat.lower() in kl:
                        raise E2ResearchAdmissionError(
                            f"{label} contains forbidden path pattern {pat!r}"
                        )
                _walk(v)
        elif isinstance(o, list):
            for item in o:
                _walk(item)
        elif isinstance(o, str):
            low = o.lower()
            for pat in _PATH_SUBSTRINGS:
                if pat.lower() in low:
                    raise E2ResearchAdmissionError(
                        f"{label} contains forbidden path pattern {pat!r}"
                    )

    _walk(obj)


def _validate_hex64(value: str, field_name: str) -> str:
    s = value.strip().lower()
    if not _HEX64_RE.fullmatch(s):
        raise ValueError(f"{field_name} must be 64-char lower-case hex")
    return s


def _validate_hex40(value: str, field_name: str) -> str:
    s = value.strip().lower()
    if not _HEX40_RE.fullmatch(s):
        raise ValueError(f"{field_name} must be 40-char lower-case hex")
    return s


def _load_expected_spec() -> dict[str, object]:
    try:
        ref = resources.files("traffictwin.evidence_admission").joinpath(
            "e2_research_admission_v1.json"
        )
        text: str = ref.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise E2ResearchAdmissionError(f"admission spec resource missing: {exc}") from exc
    except OSError as exc:
        raise E2ResearchAdmissionError(f"admission spec read failed: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise E2ResearchAdmissionError(f"admission spec is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise E2ResearchAdmissionError("admission spec top-level must be object")
    _assert_no_paths_or_secrets(data, label="admission spec")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise E2ResearchAdmissionError(f"admission spec schema_version must be {SCHEMA_VERSION!r}")
    if data.get("standing") != STANDING:
        raise E2ResearchAdmissionError(f"admission spec standing must be {STANDING!r}")
    if data.get("admission_mode") != ADMISSION_MODE:
        raise E2ResearchAdmissionError(f"admission spec admission_mode must be {ADMISSION_MODE!r}")
    expected = data.get("expected")
    if not isinstance(expected, dict):
        raise E2ResearchAdmissionError("admission spec missing expected dict")
    pkg_fp = expected.get("package_fingerprint")
    if not isinstance(pkg_fp, str):
        raise E2ResearchAdmissionError(
            "admission spec expected.package_fingerprint is required and must be string"
        )
    try:
        _validate_hex64(pkg_fp, "expected package_fingerprint")
    except ValueError as exc:
        raise E2ResearchAdmissionError(
            f"admission spec package_fingerprint invalid: {exc}"
        ) from exc
    if pkg_fp.strip().lower() != EXPECTED_PACKAGE_FINGERPRINT:
        raise E2ResearchAdmissionError("admission spec package_fingerprint drift")
    return data


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        frozen=True,
    )


class PerSeedSummary(StrictModel):
    per_seed: list[float] = Field(description="per-seed values")
    mean: float = Field(description="mean")
    ci_lower: float = Field(description="ci_lower")
    ci_upper: float = Field(description="ci_upper")

    @field_validator("per_seed")
    @classmethod
    def _validate_per_seed(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError("per_seed must contain exactly 4 values")
        return [float(x) for x in v]


class MeanCISummary(StrictModel):
    mean: float = Field(description="mean")
    ci_lower: float = Field(description="ci_lower")
    ci_upper: float = Field(description="ci_upper")


class E2ResearchAdmissionReceipt(StrictModel):
    """Deterministic owner-authorized admission receipt."""

    schema_version: Literal["e2_research_admission_v1"] = Field(
        description="Admission spec schema version"
    )
    standing: Literal["OWNER-AUTHORIZED PRODUCT ADMISSION"] = Field(
        description="Exactly OWNER-AUTHORIZED PRODUCT ADMISSION"
    )
    admission_mode: Literal["ADMITTED_RESEARCH"] = Field(
        description="Available only on exact match"
    )
    research_heads: dict[str, str] = Field(description="E2b/E2c/E2d code commits (40 hex)")
    manifests: dict[str, str] = Field(description="E2b/E2c/E2d manifest SHA-256 (64 hex)")
    actor_sha256: str = Field(description="Actor SHA-256 (64 hex)")
    trace_sha256: str = Field(description="Trace SHA-256 (64 hex)")
    replication_unit: Literal["fleet_draw"] = Field(description="Replication unit")
    evaluator_seed: Literal[0] = Field(description="Evaluator seed")
    package_fingerprint: str = Field(description="64-char hex package fingerprint")
    receipt_fingerprint: str = Field(description="64-char hex receipt fingerprint")
    e2b_offered_attainment: dict[str, float] = Field(description="E2b off/jsq/ingress_dla/dla")
    e2c_dla_minus_ingress: PerSeedSummary = Field(description="E2c per-seed/mean/CI")
    e2d_per_task_minus_ingress: PerSeedSummary = Field(description="E2d per-seed/mean/CI")
    e2d_per_task_minus_common_target: MeanCISummary = Field(
        description="Per-task minus common-target summary"
    )

    @field_validator("research_heads")
    @classmethod
    def _validate_heads(cls, v: dict[str, str]) -> dict[str, str]:
        if set(v.keys()) != {"e2b", "e2c", "e2d"}:
            raise ValueError("research_heads must contain exactly e2b, e2c, e2d")
        for k, val in v.items():
            _validate_hex40(val, f"research_heads[{k}]")
        return {k: val.strip().lower() for k, val in v.items()}

    @field_validator("manifests")
    @classmethod
    def _validate_manifests(cls, v: dict[str, str]) -> dict[str, str]:
        if set(v.keys()) != {"e2b", "e2c", "e2d"}:
            raise ValueError("manifests must contain exactly e2b, e2c, e2d")
        for k, val in v.items():
            _validate_hex64(val, f"manifests[{k}]")
        return {k: val.strip().lower() for k, val in v.items()}

    @field_validator("actor_sha256", "trace_sha256", "package_fingerprint", "receipt_fingerprint")
    @classmethod
    def _validate_hex64_field(cls, v: str) -> str:
        return _validate_hex64(v, "fingerprint")

    @field_validator("e2b_offered_attainment")
    @classmethod
    def _validate_e2b(cls, v: dict[str, float]) -> dict[str, float]:
        if set(v.keys()) != {"off", "jsq", "ingress_dla", "dla"}:
            raise ValueError("e2b_offered_attainment must contain off, jsq, ingress_dla, dla")
        return {k: float(val) for k, val in v.items()}

    @model_validator(mode="after")
    def _validate_standing_and_receipt(self) -> E2ResearchAdmissionReceipt:
        if self.standing != STANDING:
            raise ValueError(f"standing must be {STANDING!r}")
        if self.admission_mode != ADMISSION_MODE:
            raise ValueError(f"admission_mode must be {ADMISSION_MODE!r}")
        dump = self.model_dump(mode="json")
        _assert_no_paths_or_secrets(dump, label="receipt")
        for k in dump:
            if k.lower() in _TIMESTAMP_KEYS:
                raise ValueError(f"receipt must not contain timestamp field {k!r}")
        expected_fp = self.computed_fingerprint()
        if self.receipt_fingerprint != expected_fp:
            raise ValueError(
                "receipt_fingerprint mismatch: "
                f"expected {expected_fp[:8]}… "
                f"got {self.receipt_fingerprint[:8]}…"
            )
        return self

    def canonical_payload(self) -> dict[str, object]:
        data: dict[str, object] = self.model_dump(mode="json")
        data.pop("receipt_fingerprint", None)
        return data

    def computed_fingerprint(self) -> str:
        return _canonical_fingerprint(self.canonical_payload())

    def verify(self) -> None:
        for name in ("actor_sha256", "trace_sha256", "package_fingerprint", "receipt_fingerprint"):
            val: str = getattr(self, name)
            if not _HEX64_RE.fullmatch(val):
                raise E2ResearchAdmissionError(f"receipt field {name} is not 64 hex")
        for name in ("e2b", "e2c", "e2d"):
            h: str = self.research_heads.get(name, "")
            if not _HEX40_RE.fullmatch(h):
                raise E2ResearchAdmissionError(f"research_heads[{name}] is not 40 hex")
            m: str = self.manifests.get(name, "")
            if not _HEX64_RE.fullmatch(m):
                raise E2ResearchAdmissionError(f"manifests[{name}] is not 64 hex")
        if self.standing != STANDING:
            raise E2ResearchAdmissionError(f"standing must be {STANDING!r}")
        if self.admission_mode != ADMISSION_MODE:
            raise E2ResearchAdmissionError(f"admission_mode must be {ADMISSION_MODE!r}")
        dump = self.model_dump(mode="json")
        _assert_no_paths_or_secrets(dump, label="receipt")
        for k in dump:
            if k.lower() in _TIMESTAMP_KEYS:
                raise E2ResearchAdmissionError(f"receipt must not contain timestamp field {k!r}")
        if self.schema_version != SCHEMA_VERSION:
            raise E2ResearchAdmissionError(f"schema_version must be {SCHEMA_VERSION!r}")
        if self.replication_unit != "fleet_draw":
            raise E2ResearchAdmissionError("replication_unit must be fleet_draw")
        if self.evaluator_seed != 0:
            raise E2ResearchAdmissionError("evaluator_seed must be 0")
        if self.receipt_fingerprint != self.computed_fingerprint():
            raise E2ResearchAdmissionError("receipt_fingerprint does not match computed binding")


def _build_receipt(package_fingerprint: str, spec: dict[str, object]) -> E2ResearchAdmissionReceipt:
    expected_obj = spec.get("expected")
    if not isinstance(expected_obj, dict):
        raise E2ResearchAdmissionError("spec missing expected")
    expected: dict[str, object] = expected_obj

    heads_obj = expected.get("research_heads")
    mans_obj = expected.get("manifests")
    if not isinstance(heads_obj, dict) or not isinstance(mans_obj, dict):
        raise E2ResearchAdmissionError("spec expected missing heads/manifests")
    research_heads: dict[str, str] = {k: str(v).strip().lower() for k, v in heads_obj.items()}
    manifests: dict[str, str] = {k: str(v).strip().lower() for k, v in mans_obj.items()}
    actor_sha256 = str(expected.get("actor_sha256", "")).strip().lower()
    trace_sha256 = str(expected.get("trace_sha256", "")).strip().lower()
    replication_unit = expected.get("replication_unit")
    evaluator_seed = expected.get("evaluator_seed")
    if replication_unit != "fleet_draw":
        raise E2ResearchAdmissionError("spec replication_unit must be fleet_draw")
    if evaluator_seed != 0:
        raise E2ResearchAdmissionError("spec evaluator_seed must be 0")

    e2b_obj = expected.get("e2b_offered_attainment")
    if not isinstance(e2b_obj, dict):
        raise E2ResearchAdmissionError("spec missing e2b_offered_attainment")
    e2b: dict[str, float] = {k: float(v) for k, v in e2b_obj.items()}

    e2c_obj = expected.get("e2c_dla_minus_ingress")
    e2d_obj = expected.get("e2d_per_task_minus_ingress")
    e2d_vs_obj = expected.get("e2d_per_task_minus_common_target")
    if (
        not isinstance(e2c_obj, dict)
        or not isinstance(e2d_obj, dict)
        or not isinstance(e2d_vs_obj, dict)
    ):
        raise E2ResearchAdmissionError("spec missing e2c/e2d groups")

    e2c = PerSeedSummary.model_validate(e2c_obj)
    e2d = PerSeedSummary.model_validate(e2d_obj)
    e2d_vs = MeanCISummary.model_validate(e2d_vs_obj)

    tmp: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "standing": STANDING,
        "admission_mode": ADMISSION_MODE,
        "research_heads": research_heads,
        "manifests": manifests,
        "actor_sha256": actor_sha256,
        "trace_sha256": trace_sha256,
        "replication_unit": replication_unit,
        "evaluator_seed": evaluator_seed,
        "package_fingerprint": package_fingerprint.strip().lower(),
        "e2b_offered_attainment": e2b,
        "e2c_dla_minus_ingress": e2c.model_dump(mode="json"),
        "e2d_per_task_minus_ingress": e2d.model_dump(mode="json"),
        "e2d_per_task_minus_common_target": e2d_vs.model_dump(mode="json"),
    }
    _assert_no_paths_or_secrets(tmp, label="receipt canonical")
    receipt_fp = _canonical_fingerprint(tmp)
    return E2ResearchAdmissionReceipt(
        schema_version=SCHEMA_VERSION,
        standing=STANDING,
        admission_mode=ADMISSION_MODE,
        research_heads=research_heads,
        manifests=manifests,
        actor_sha256=actor_sha256,
        trace_sha256=trace_sha256,
        replication_unit="fleet_draw",
        evaluator_seed=0,
        package_fingerprint=package_fingerprint.strip().lower(),
        receipt_fingerprint=receipt_fp,
        e2b_offered_attainment=e2b,
        e2c_dla_minus_ingress=e2c,
        e2d_per_task_minus_ingress=e2d,
        e2d_per_task_minus_common_target=e2d_vs,
    )


def _validate_package_exact(package: E2ResearchEvidencePackage) -> None:
    spec = _load_expected_spec()
    expected_obj = spec.get("expected")
    if not isinstance(expected_obj, dict):
        raise E2ResearchAdmissionError("spec missing expected")
    expected: dict[str, object] = expected_obj

    exp_heads = expected.get("research_heads")
    exp_mans = expected.get("manifests")
    if not isinstance(exp_heads, dict) or not isinstance(exp_mans, dict):
        raise E2ResearchAdmissionError("spec heads/manifests malformed")
    for k in ("e2b", "e2c", "e2d"):
        actual_head = getattr(package.source_identities.research_heads, k)
        exp_head = str(exp_heads.get(k, "")).strip().lower()
        if actual_head.strip().lower() != exp_head:
            raise E2ResearchAdmissionError(f"research_heads[{k}] mismatch")
    for k in ("e2b", "e2c", "e2d"):
        actual_man = package.source_identities.manifest_sha256_by_study.get(k, "")
        exp_man = str(exp_mans.get(k, "")).strip().lower()
        if actual_man.strip().lower() != exp_man:
            raise E2ResearchAdmissionError(f"manifests[{k}] mismatch")
    if (
        package.source_identities.actor.sha256.strip().lower()
        != str(expected.get("actor_sha256", "")).strip().lower()
    ):
        raise E2ResearchAdmissionError("actor_sha256 mismatch")
    if (
        package.source_identities.trace.sha256.strip().lower()
        != str(expected.get("trace_sha256", "")).strip().lower()
    ):
        raise E2ResearchAdmissionError("trace_sha256 mismatch")
    if package.replication_unit != expected.get("replication_unit"):
        raise E2ResearchAdmissionError(
            "replication_unit mismatch: "
            f"expected {expected.get('replication_unit')!r} "
            f"got {package.replication_unit!r}"
        )
    if package.evaluator_seed != expected.get("evaluator_seed"):
        raise E2ResearchAdmissionError(
            "evaluator_seed mismatch: "
            f"expected {expected.get('evaluator_seed')} "
            f"got {package.evaluator_seed}"
        )
    exp_e2b = expected.get("e2b_offered_attainment")
    if not isinstance(exp_e2b, dict):
        raise E2ResearchAdmissionError("spec e2b_offered_attainment malformed")
    obs_by_fig: dict[str, float] = {o.figure_id: float(o.value) for o in package.observations}
    for key, fig in [
        ("off", "fig1_e2b_offered_attainment_off"),
        ("jsq", "fig1_e2b_offered_attainment_jsq"),
        ("dla", "fig1_e2b_offered_attainment_dla"),
        ("ingress_dla", "fig1_e2b_offered_attainment_ingress_dla"),
    ]:
        exp_val = float(exp_e2b.get(key, 999))
        act_val = obs_by_fig.get(fig)
        if act_val is None:
            raise E2ResearchAdmissionError(f"missing observation {fig!r}")
        if float(act_val) != float(exp_val):
            raise E2ResearchAdmissionError(
                f"e2b_offered_attainment[{key}] mismatch: expected {exp_val!r} got {act_val!r}"
            )
    exp_e2c = expected.get("e2c_dla_minus_ingress")
    exp_e2d = expected.get("e2d_per_task_minus_ingress")
    exp_vs = expected.get("e2d_per_task_minus_common_target")
    if (
        not isinstance(exp_e2c, dict)
        or not isinstance(exp_e2d, dict)
        or not isinstance(exp_vs, dict)
    ):
        raise E2ResearchAdmissionError("spec e2c/e2d groups malformed")

    pd_by_id: dict[str, list[float]] = {
        pd.comparison_id: [float(x) for x in pd.per_seed_values]
        for pd in package.paired_differences
    }
    ds_by_id: dict[str, object] = {ds.comparison_id: ds for ds in package.declared_summaries}

    def _check_per_seed_group(key: str, exp_group: dict[str, object]) -> None:
        exp_per = exp_group.get("per_seed")
        if not isinstance(exp_per, list):
            raise E2ResearchAdmissionError(f"{key} per_seed malformed")
        act_per = pd_by_id.get(key)
        if act_per is None:
            raise E2ResearchAdmissionError(f"missing paired_difference {key!r}")
        if [float(x) for x in act_per] != [float(x) for x in exp_per]:
            raise E2ResearchAdmissionError(
                f"{key} per_seed mismatch: expected {exp_per!r} got {act_per!r}"
            )
        ds_obj = ds_by_id.get(key)
        if ds_obj is None:
            raise E2ResearchAdmissionError(f"missing declared_summary {key!r}")
        # ds is DeclaredSummary, access via attribute
        ds = ds_obj
        for field, exp_key in [("mean", "mean"), ("lower", "ci_lower"), ("upper", "ci_upper")]:
            exp_val_obj = exp_group.get(exp_key)
            act_val = getattr(ds, field)
            if exp_val_obj is None or act_val is None:
                raise E2ResearchAdmissionError(f"{key} {exp_key} missing")
            exp_f_tmp = float(exp_val_obj) if isinstance(exp_val_obj, (int, float, str)) else 0.0
            act_f_tmp = float(act_val) if isinstance(act_val, (int, float, str)) else 0.0
            if act_f_tmp != exp_f_tmp:
                raise E2ResearchAdmissionError(
                    f"{key} {exp_key} mismatch: expected {exp_val_obj!r} got {act_val!r}"
                )

    _check_per_seed_group(
        "e2c_dla_minus_ingress",
        exp_e2c,
    )
    _check_per_seed_group(
        "e2d_per_task_minus_ingress",
        exp_e2d,
    )
    # vs common has no per_seed, only mean/CI
    vs_ds = ds_by_id.get("e2d_per_task_minus_dla")
    if vs_ds is None:
        raise E2ResearchAdmissionError("missing declared_summary e2d_per_task_minus_dla")
    for field, exp_key in [("mean", "mean"), ("lower", "ci_lower"), ("upper", "ci_upper")]:
        exp_val_obj = exp_vs.get(exp_key)
        act_val = getattr(vs_ds, field)
        if exp_val_obj is None or act_val is None:
            raise E2ResearchAdmissionError(f"e2d_per_task_minus_common_target {exp_key} missing")
        exp_f2 = float(exp_val_obj) if isinstance(exp_val_obj, (int, float, str)) else 0.0
        act_f2 = float(act_val) if isinstance(act_val, (int, float, str)) else 0.0
        if act_f2 != exp_f2:
            raise E2ResearchAdmissionError(
                f"e2d_per_task_minus_common_target {exp_key} mismatch: "
                f"expected {exp_val_obj!r} got {act_val!r}"
            )
    # Package fingerprint check
    fp = package.fingerprint()
    if fp != EXPECTED_PACKAGE_FINGERPRINT:
        raise E2ResearchAdmissionError(
            "package fingerprint mismatch: "
            f"expected {EXPECTED_PACKAGE_FINGERPRINT[:8]}… "
            f"got {fp[:8]}…"
        )
    _assert_no_paths_or_secrets(package.model_dump(mode="json"), label="package")


def admit_e2_research(package: E2ResearchEvidencePackage) -> E2ResearchAdmissionReceipt:
    """Admit a built-in E2 research package — fail-closed.

    Binds schema validation, every expected head/manifest, actor/trace,
    replication unit/evaluator seed and the exact package fingerprint.
    Returns an ``E2ResearchAdmissionReceipt`` with standing
    ``OWNER-AUTHORIZED PRODUCT ADMISSION`` and mode ``ADMITTED_RESEARCH``
    only on exact match; otherwise raises :class:`E2ResearchAdmissionError`.
    """
    if not isinstance(package, E2ResearchEvidencePackage):
        raise E2ResearchAdmissionError(
            f"package must be E2ResearchEvidencePackage, got {type(package).__name__}"
        )
    # Strict package fingerprint path-free check via model validation already
    # Exhaustive pinned validation
    _validate_package_exact(package)
    package_fp = package.fingerprint()
    spec = _load_expected_spec()
    receipt = _build_receipt(package_fp, spec)
    try:
        receipt.verify()
    except E2ResearchAdmissionError:
        raise
    except ValueError as exc:
        raise E2ResearchAdmissionError(f"receipt verification failed: {exc}") from exc
    return receipt


def load_admitted_builtin_e2_research() -> tuple[
    E2ResearchEvidencePackage, E2ResearchAdmissionReceipt
]:
    """Load the built-in package and return ``(package, receipt)`` on exact match.

    Uses Lane 03's artifact loader; fails closed on any loader/schema/
    fingerprint/source/value drift and exposes no admitted result on failure.
    No fallback package or alternate schema.
    """
    try:
        pkg: E2ResearchEvidencePackage = load_builtin_e2_research()
    except FileNotFoundError as exc:
        raise E2ResearchAdmissionError(f"built-in resource missing: {exc}") from exc
    except ValueError as exc:
        raise E2ResearchAdmissionError(f"builtin validation failed: {exc}") from exc
    except OSError as exc:
        raise E2ResearchAdmissionError(f"builtin load failed: {exc}") from exc
    receipt = admit_e2_research(pkg)
    return pkg, receipt


__all__ = [
    "ADMISSION_MODE",
    "E2ResearchAdmissionError",
    "E2ResearchAdmissionReceipt",
    "EXPECTED_PACKAGE_FINGERPRINT",
    "STANDING",
    "admit_e2_research",
    "load_admitted_builtin_e2_research",
]
