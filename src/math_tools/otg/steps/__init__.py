"""Step solvers for the OTG (online trajectory generation) subsystem.

Private subpackage (Swift ``internal`` visibility): every class here ports
one Swift step-solver class 1:1 (``otg.md`` §Module layout). Nothing here is
re-exported from ``math_tools.otg``'s public surface -- see
``.claude/specs/otg.md`` §Module layout's "private" note.
"""

from __future__ import annotations
