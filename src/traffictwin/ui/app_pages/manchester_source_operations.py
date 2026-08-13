"""Manchester Source Operations app page — additive Lane 14 page.

Lane-local page reachable via direct import; snapshot quality diagnostics
use latest exact pointer ordered by ``(retrieved_at_utc, registration_id)``
tie-break, bounded row counts, and distinguish measured 0 from unmeasured ``—``.
"""

from traffictwin.ui.pages.manchester_source_operations import render

render()
