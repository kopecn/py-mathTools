"""``SpectralMixin``: FFT / PSD / spectrogram / mel-spectrogram / spectral features.

See ``.claude/specs/waveformDsp.md`` §Family contracts (``SpectralMixin``),
§Numerical conventions, §Compliance 1-2. Swift reference:
``Waveform1D/Extensions/Waveform1D-FFT.swift``,
``Waveform1D/Extensions/Waveform1D-Spectrogram.swift``.

Backing: ``np.fft.rfft`` (one-sided FFT), ``scipy.signal.welch`` (Welch PSD),
``scipy.signal.spectrogram`` (STFT magnitude surface), a hand-built
triangular mel filterbank (numpy, applied to the STFT magnitude surface),
per waveformDsp.md's family-contract table. Window arguments
(``WaveformWindowType``) are mapped to concrete window arrays via
``scipy.signal.get_window`` directly in this module (chunk 21's own design
constraint -- chunk 28's ``WindowingMixin`` is for user-facing window
utilities, not a dependency of this one; §Organization/§Compliance 2 forbid
importing a sibling mixin module here regardless).

**``spectral_features`` field-set divergence from the Swift reference.** The
chunk doc for this module says to "mirror [the Swift ``extractSpectralFeatures``
struct's] fields exactly", but that struct (``Waveform1D/Support/
WaveformSpectralFeatures.swift``) is a *per-time-frame* result computed from
a spectrogram (``spectralCentroids: [PrecisionTimestamp]``,
``spectralRolloffs: [PrecisionTimeInterval]``, ``spectralFluxes: [Double]``,
``timeFrames: [PrecisionTimestamp]``) -- not the four scalar whole-spectrum
statistics the chunk doc's own method-list bullet names (``centroid, spread,
rolloff, flatness``). The Python ``WaveformSpectralFeatures`` dataclass
already shipped in ``waveforms/support.py`` (chunk 14, merged before this
chunk) is the latter shape (``centroid: float``, ``spread: float``,
``rolloff: float``, ``flatness: float``) and waveformDsp.md §Support
descriptor types already documents it that way. This module implements
against the already-accepted scalar shape (a single whole-spectrum summary
computed from :func:`fft`, matching the spec/support.py that predate this
chunk) rather than reopening ``support.py`` to switch to a per-frame
time-series shape -- consistent with the spec's stated policy that "parity
is judged per capability, not per Swift overload" when scipy/the existing
Python design is the better-tested equivalent. No spec or support.py change
was needed since both already agree with this shape; only the (stale)
chunk-doc bullet disagreed.

Imports only ``scipy``/``numpy`` plus ``dsp/_protocol.py``/``dsp/_common.py``
and ``waveforms/support.py`` (for the enum/descriptor types) -- no sibling
mixin imports (waveformDsp.md §Organization / §Compliance 2).

**Not** ``class SpectralMixin(WaveformProtocol)``: see ``dsp/_calc.py``'s
module docstring / waveformDsp.md §Organization for the full account of why
mixins type ``self`` as ``WaveformProtocol`` on each method instead of
nominally subclassing it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.signal import get_window, welch
from scipy.signal import spectrogram as _scipy_spectrogram

from math_tools.waveforms.dsp._common import float_seconds
from math_tools.waveforms.dsp._protocol import WaveformProtocol
from math_tools.waveforms.support import (
    WaveformMelSpectrogram,
    WaveformPSDScaling,
    WaveformSpectralFeatures,
    WaveformSpectrogram,
    WaveformSpectrum,
    WaveformWindowType,
)

_DEFAULT_NPERSEG = 256
_DEFAULT_OVERLAP = 0.5
_DEFAULT_N_MELS = 40
_DEFAULT_ROLLOFF_FRACTION = 0.95

# scipy's `get_window` has no default shape parameter for "kaiser" -- the family
# contract exposes no beta of its own, so this module fixes one general-purpose
# value (comparable sidelobe suppression to a Blackman window) rather than adding
# an extra parameter no other window type needs. Chunk 28's user-facing window
# utilities may expose beta directly if a caller ever needs it (YAGNI).
_DEFAULT_KAISER_BETA = 14.0

_WINDOW_NAME_MAP: dict[WaveformWindowType, str] = {
    WaveformWindowType.HANN: "hann",
    WaveformWindowType.HAMMING: "hamming",
    WaveformWindowType.BLACKMAN: "blackman",
    WaveformWindowType.BARTLETT: "bartlett",
    WaveformWindowType.RECTANGULAR: "boxcar",
}


def _scipy_window_spec(window: WaveformWindowType) -> str | tuple[str, float]:
    """``WaveformWindowType`` -> a ``scipy.signal.get_window``-compatible spec."""
    if window is WaveformWindowType.KAISER:
        return ("kaiser", _DEFAULT_KAISER_BETA)
    return _WINDOW_NAME_MAP[window]


def _window_array(window: WaveformWindowType, length: int) -> npt.NDArray[np.float64]:
    """The concrete window coefficients for ``window`` at ``length`` samples."""
    result: npt.NDArray[np.float64] = get_window(_scipy_window_spec(window), length)
    return result


def _resolve_nperseg(nperseg: int | None, sample_count: int, op_name: str) -> int:
    """Resolve the analysis segment length: default ``min(256, sample_count)``, else
    the caller's explicit value (validated against ``sample_count``)."""
    if nperseg is None:
        return min(_DEFAULT_NPERSEG, sample_count)
    if nperseg < 1:
        raise ValueError(f"SpectralMixin.{op_name}: nperseg must be >= 1, got {nperseg}")
    if nperseg > sample_count:
        raise ValueError(
            f"SpectralMixin.{op_name}: nperseg ({nperseg}) exceeds sample_count "
            f"({sample_count})"
        )
    return nperseg


def _require_valid_overlap(overlap: float, op_name: str) -> None:
    if not (0.0 <= overlap < 1.0):
        raise ValueError(f"SpectralMixin.{op_name}: overlap must be in [0, 1), got {overlap}")


def _stft_magnitude_surface(
    values: npt.NDArray[Any],
    fs: float,
    window: WaveformWindowType,
    nperseg: int,
    overlap: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """``(times, frequencies, magnitudes[time, frequency])`` via ``scipy.signal.spectrogram``.

    Shared by :meth:`SpectralMixin.spectrogram` and
    :meth:`SpectralMixin.mel_spectrogram` so both stay exactly consistent
    about the STFT parameters and the ``[time, frequency]`` axis convention
    (``waveforms/support.py``'s ``WaveformSpectrogram`` docstring; scipy's
    native ``Sxx`` is ``[frequency, time]``, transposed here).
    """
    noverlap = int(nperseg * overlap)
    window_array = _window_array(window, nperseg)
    frequencies, times, sxx = _scipy_spectrogram(
        values,
        fs=fs,
        window=window_array,
        nperseg=nperseg,
        noverlap=noverlap,
        mode="magnitude",
    )
    magnitudes = np.asarray(sxx, dtype=np.float64).T
    return (
        np.asarray(times, dtype=np.float64),
        np.asarray(frequencies, dtype=np.float64),
        magnitudes,
    )


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * float(np.log10(1.0 + hz / 700.0))


def _mel_to_hz(mel: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    result: npt.NDArray[np.float64] = 700.0 * (10.0 ** (mel / 2595.0) - 1.0)
    return result


def _mel_filterbank(
    frequency_bins_hz: npt.NDArray[np.float64],
    n_mels: int,
    min_frequency_hz: float,
    max_frequency_hz: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Triangular mel filterbank: ``(filterbank, mel_center_frequencies_hz)``.

    ``filterbank`` has shape ``(n_mels, len(frequency_bins_hz))``. Each row
    is a triangle over ``[left, center, right]`` mel-spaced edges (converted
    back to Hz), then normalized so it sums to ``~1`` whenever its support is
    fully inside ``frequency_bins_hz`` (waveformDsp.md chunk 21's TDD step 1)
    -- a row-sum normalization, not the usual peak-height-1 triangle or
    Slaney-style bandwidth normalization.
    """
    mel_min = _hz_to_mel(min_frequency_hz)
    mel_max = _hz_to_mel(max_frequency_hz)
    mel_edges = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_edges = _mel_to_hz(mel_edges)

    filterbank = np.zeros((n_mels, frequency_bins_hz.shape[0]), dtype=np.float64)
    for m in range(n_mels):
        left, center, right = hz_edges[m], hz_edges[m + 1], hz_edges[m + 2]
        rising = (
            (frequency_bins_hz - left) / (center - left)
            if center > left
            else np.zeros_like(frequency_bins_hz)
        )
        falling = (
            (right - frequency_bins_hz) / (right - center)
            if right > center
            else np.zeros_like(frequency_bins_hz)
        )
        weights = np.clip(np.minimum(rising, falling), 0.0, None)
        row_sum = float(np.sum(weights))
        filterbank[m, :] = weights / row_sum if row_sum > 0.0 else weights

    mel_centers_hz: npt.NDArray[np.float64] = hz_edges[1:-1].astype(np.float64)
    return filterbank, mel_centers_hz


class SpectralMixin:
    """Adds FFT/PSD/spectrogram/mel-spectrogram/spectral-feature methods to a
    ``WaveformProtocol`` host."""

    def fft(self: WaveformProtocol) -> WaveformSpectrum:
        """One-sided FFT (``np.fft.rfft``); frequencies in Hz from ``dt``.

        Raises:
            ValueError: If the waveform has fewer than 2 samples.
        """
        values = np.asarray(self.values, dtype=np.float64)
        n = values.shape[0]
        if n < 2:
            raise ValueError(f"SpectralMixin.fft requires at least 2 samples, got {n}")
        spectrum = np.fft.rfft(values)
        frequencies = np.fft.rfftfreq(n, d=float_seconds(self.dt))
        return WaveformSpectrum(
            frequencies=frequencies.astype(np.float64),
            magnitudes=np.abs(spectrum).astype(np.float64),
            phases=np.angle(spectrum).astype(np.float64),
        )

    def power_spectral_density(
        self: WaveformProtocol,
        window: WaveformWindowType = WaveformWindowType.HANN,
        scaling: WaveformPSDScaling = WaveformPSDScaling.DENSITY,
        nperseg: int | None = None,
    ) -> WaveformSpectrum:
        """Welch's-method power spectral density (``scipy.signal.welch``).

        ``phases`` is always all-zero: Welch's method discards phase by
        construction (it averages the power across overlapping segments).

        Raises:
            ValueError: If the waveform has fewer than 2 samples, or
                ``nperseg`` is out of range.
        """
        values = np.asarray(self.values, dtype=np.float64)
        n = values.shape[0]
        if n < 2:
            raise ValueError(
                f"SpectralMixin.power_spectral_density requires at least 2 samples, got {n}"
            )
        resolved_nperseg = _resolve_nperseg(nperseg, n, "power_spectral_density")
        window_array = _window_array(window, resolved_nperseg)
        frequencies, psd = welch(
            values,
            fs=self.sampling_frequency_hz,
            window=window_array,
            nperseg=resolved_nperseg,
            scaling=scaling.value,
        )
        magnitudes = np.asarray(psd, dtype=np.float64)
        return WaveformSpectrum(
            frequencies=np.asarray(frequencies, dtype=np.float64),
            magnitudes=magnitudes,
            phases=np.zeros_like(magnitudes),
        )

    def spectrogram(
        self: WaveformProtocol,
        window: WaveformWindowType = WaveformWindowType.HANN,
        nperseg: int | None = None,
        overlap: float = _DEFAULT_OVERLAP,
    ) -> WaveformSpectrogram:
        """Short-time-Fourier-transform magnitude surface (``scipy.signal.spectrogram``).

        Raises:
            ValueError: If the waveform has fewer than 2 samples, ``overlap``
                is outside ``[0, 1)``, or ``nperseg`` is out of range.
        """
        values = np.asarray(self.values, dtype=np.float64)
        n = values.shape[0]
        if n < 2:
            raise ValueError(f"SpectralMixin.spectrogram requires at least 2 samples, got {n}")
        _require_valid_overlap(overlap, "spectrogram")
        resolved_nperseg = _resolve_nperseg(nperseg, n, "spectrogram")
        times, frequencies, magnitudes = _stft_magnitude_surface(
            values, self.sampling_frequency_hz, window, resolved_nperseg, overlap
        )
        return WaveformSpectrogram(times=times, frequencies=frequencies, magnitudes=magnitudes)

    def mel_spectrogram(
        self: WaveformProtocol,
        n_mels: int = _DEFAULT_N_MELS,
        window: WaveformWindowType = WaveformWindowType.HANN,
        nperseg: int | None = None,
        overlap: float = _DEFAULT_OVERLAP,
        min_frequency_hz: float = 0.0,
        max_frequency_hz: float | None = None,
    ) -> WaveformMelSpectrogram:
        """Mel-scale spectrogram: a triangular mel filterbank (hand-built, numpy)
        applied to the STFT magnitude surface (``scipy.signal.spectrogram``-backed).

        Raises:
            ValueError: If the waveform has fewer than 2 samples, ``n_mels``
                is < 1, ``overlap`` is outside ``[0, 1)``, ``nperseg`` is out
                of range, or the resolved frequency band is empty/inverted.
        """
        values = np.asarray(self.values, dtype=np.float64)
        n = values.shape[0]
        if n < 2:
            raise ValueError(
                f"SpectralMixin.mel_spectrogram requires at least 2 samples, got {n}"
            )
        if n_mels < 1:
            raise ValueError(f"SpectralMixin.mel_spectrogram: n_mels must be >= 1, got {n_mels}")
        _require_valid_overlap(overlap, "mel_spectrogram")
        resolved_nperseg = _resolve_nperseg(nperseg, n, "mel_spectrogram")
        resolved_max_frequency_hz = (
            max_frequency_hz if max_frequency_hz is not None else self.sampling_frequency_hz / 2.0
        )
        if resolved_max_frequency_hz <= min_frequency_hz:
            raise ValueError(
                "SpectralMixin.mel_spectrogram: max_frequency_hz must exceed min_frequency_hz "
                f"(got min={min_frequency_hz}, max={resolved_max_frequency_hz})"
            )

        times, frequencies, magnitudes = _stft_magnitude_surface(
            values, self.sampling_frequency_hz, window, resolved_nperseg, overlap
        )
        filterbank, mel_centers_hz = _mel_filterbank(
            frequency_bins_hz=frequencies,
            n_mels=n_mels,
            min_frequency_hz=min_frequency_hz,
            max_frequency_hz=resolved_max_frequency_hz,
        )
        mel_magnitudes = magnitudes @ filterbank.T
        return WaveformMelSpectrogram(
            times=times, mel_frequencies=mel_centers_hz, magnitudes=mel_magnitudes
        )

    def spectral_features(
        self: WaveformProtocol, rolloff_fraction: float = _DEFAULT_ROLLOFF_FRACTION
    ) -> WaveformSpectralFeatures:
        """Whole-spectrum summary statistics from the FFT magnitude spectrum.

        - ``centroid``: the magnitude-weighted mean frequency.
        - ``spread``: the magnitude-weighted standard deviation around the centroid.
        - ``rolloff``: the frequency below which ``rolloff_fraction`` of the
          total magnitude is contained.
        - ``flatness``: geometric-mean-over-arithmetic-mean of the magnitude
          spectrum (Wiener entropy; ~0 = tonal, ~1 = noise-like).

        See the module docstring for why this returns the scalar
        (``centroid``/``spread``/``rolloff``/``flatness``) shape already
        defined in ``waveforms/support.py`` rather than the Swift reference's
        per-time-frame shape.

        Raises:
            ValueError: If the waveform has fewer than 2 samples, or
                ``rolloff_fraction`` is outside ``(0, 1]``.
        """
        values = np.asarray(self.values, dtype=np.float64)
        n = values.shape[0]
        if n < 2:
            raise ValueError(
                f"SpectralMixin.spectral_features requires at least 2 samples, got {n}"
            )
        if not (0.0 < rolloff_fraction <= 1.0):
            raise ValueError(
                "SpectralMixin.spectral_features: rolloff_fraction must be in (0, 1], "
                f"got {rolloff_fraction}"
            )

        magnitudes = np.abs(np.fft.rfft(values))
        frequencies = np.fft.rfftfreq(n, d=float_seconds(self.dt))
        total_energy = float(np.sum(magnitudes))
        if total_energy <= 0.0:
            return WaveformSpectralFeatures(centroid=0.0, spread=0.0, rolloff=0.0, flatness=0.0)

        centroid = float(np.sum(frequencies * magnitudes) / total_energy)
        spread = float(
            np.sqrt(np.sum(magnitudes * (frequencies - centroid) ** 2) / total_energy)
        )

        cumulative = np.cumsum(magnitudes)
        rolloff_index = int(np.searchsorted(cumulative, rolloff_fraction * total_energy))
        rolloff_index = min(rolloff_index, frequencies.shape[0] - 1)
        rolloff = float(frequencies[rolloff_index])

        nonzero_magnitudes = magnitudes[magnitudes > 0.0]
        if nonzero_magnitudes.size == 0:
            flatness = 0.0
        else:
            geometric_mean = float(np.exp(np.mean(np.log(nonzero_magnitudes))))
            arithmetic_mean = float(np.mean(magnitudes))
            flatness = geometric_mean / arithmetic_mean if arithmetic_mean > 0.0 else 0.0

        return WaveformSpectralFeatures(
            centroid=centroid, spread=spread, rolloff=rolloff, flatness=flatness
        )


__all__ = ["SpectralMixin"]
