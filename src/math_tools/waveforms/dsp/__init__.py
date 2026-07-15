"""DSP mixin substrate for ``Waveform1D`` (protocol + shared helpers).

See ``.claude/specs/waveformDsp.md``. This package holds the per-family
mixin modules (chunks 18-30) plus the shared ``WaveformProtocol`` typing
contract (``_protocol.py``) and cross-mixin helpers (``_common.py``); no
mixin is composed into ``Waveform1D`` until the later "compose" chunk.
"""
