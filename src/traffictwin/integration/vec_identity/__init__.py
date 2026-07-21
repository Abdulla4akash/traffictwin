"""Occupancy-bounded VEC vehicle identity (VEC-03)."""

from traffictwin.integration.vec_identity.models import (
    VecIdentityContract,
    VecIdentityCoverageReport,
    VecIdentityFinding,
    VecIdentityFindingCode,
    VecIdentitySnapshot,
    VecVehicleMobilityObservation,
    vec_identity_contract,
)
from traffictwin.integration.vec_identity.service import (
    VecIdentityError,
    build_vehicle_identity_snapshot,
    iter_vehicle_mobility,
    resolve_vehicle_identity,
    trace_fingerprint,
)

__all__ = [
    "VecIdentityContract",
    "VecIdentityCoverageReport",
    "VecIdentityError",
    "VecIdentityFinding",
    "VecIdentityFindingCode",
    "VecIdentitySnapshot",
    "VecVehicleMobilityObservation",
    "build_vehicle_identity_snapshot",
    "iter_vehicle_mobility",
    "resolve_vehicle_identity",
    "trace_fingerprint",
    "vec_identity_contract",
]
