"""Permission-bounded VEC dissertation fixture publication (VEC-11)."""

from traffictwin.integration.vec_publication.models import (
    VecDissertationPackContract,
    VecDissertationPackManifest,
    VecSanitisedMatchedSample,
    vec_dissertation_pack_contract,
)
from traffictwin.integration.vec_publication.service import (
    VecDissertationPackError,
    derive_sanitised_matched_sample,
    render_vec_dissertation_pack,
    verify_vec_dissertation_pack,
    write_vec_dissertation_pack,
)

__all__ = [
    "VecDissertationPackContract",
    "VecDissertationPackError",
    "VecDissertationPackManifest",
    "VecSanitisedMatchedSample",
    "derive_sanitised_matched_sample",
    "render_vec_dissertation_pack",
    "vec_dissertation_pack_contract",
    "verify_vec_dissertation_pack",
    "write_vec_dissertation_pack",
]
