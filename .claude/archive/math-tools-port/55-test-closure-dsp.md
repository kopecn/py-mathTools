---
chunk: 55-test-closure-dsp
track: F
status: complete
depends_on: [53]
spec: ../specs/waveformDsp.md
last_updated: 2026-07-23
semver: 0.0.2
author: Nicholas Bergantz
---

# 55 — Test-coverage closure: DSP mixins (Track D)

## Origin

The 18 class **(b)** findings from the Track D audit — the track's dominant
defect class, concentrated in `FilteringMixin` (6), `SpectralMixin` (5), and
`ResamplingMixin` (5). Runs after chunk 53 so window-convention tests pin the
reconciled contract.

**Tests only. No `src/` changes.** If a test exposes a genuine defect, stop and
report it in the resolution notes.

This chunk is large. Execute it family by family, running the suite after each
family, rather than writing everything and running once.

## Files

- Edit: `tests/waveforms/dsp/test_correlation.py`, `test_envelope.py`,
  `test_spectral.py`, `test_filtering.py`, `test_peaks.py`, `test_phase.py`,
  `test_resampling.py`, `test_time_alignment.py`, `test_triggers.py`,
  `test_windowing.py`, `test_zero_crossings.py`

## Gaps to close, by family

**Highest value first** — the first three are spec-mandated behaviors with zero
coverage:

1. **Filtering `causal=True`** (`_filtering.py:208,228,251,278`) — never set to
   `True` anywhere (`grep -rn causal tests/` returns nothing), so the `lfilter`
   branch of `_apply_iir` (`:136`) is entirely untested despite waveformDsp.md
   §Numerical conventions mandating the flag.
2. **`savitzky_golay_filter(deriv > 0)`** (`_filtering.py:356`) — the only place
   `delta=dt_seconds` is applied. A wrong `delta` silently returns per-sample
   instead of per-second derivatives. Verified live: `(11, 3, deriv=1)` on a
   50 Hz sine returns ~322, i.e. correct 1/s units — pin that number.
3. **`resampled` value assertions** (`_resampling.py:205`) — currently checks
   only `dt`, length, `t0`. waveformDsp.md §Compliance 1 names by title
   "`resampled` ×2 then ÷2 round-trips (rtol 1e-3, interior)"; the suite
   substitutes `interpolated(2).decimated(2)`. Add the spec's actual case.

**Filtering**
4. `_validate_order` (`:63`, `order < 1`) never triggered for any Butterworth
   method — the raise-don't-clamp policy's load-bearing path.
5. `_validate_cutoff` lower bound (`:68`, `cutoff_hz <= 0`) untested.
6. `frequency_response` (`:406`) — `phases` never asserted; BAND_PASS and
   BAND_STOP never requested.
7. `exponential_filter` (`:162`) — pinned only at `alpha=1.0`, first-sample
   equality, and `values[20] < 1.0`. A swapped `alpha`/`1−alpha` survives all
   three. Compute the closed form `y[i] = α·x[i] + (1−α)·y[i−1]` for a specific `i`.

**Spectral**
8. `scaling: WaveformPSDScaling` (`:232`) never passed. `DENSITY` and `SPECTRUM`
   differ ~11× on a 50 Hz tone at fs=2 kHz — pin both.
9. `window: WaveformWindowType` (`:231,268,292`) never varied from `HANN`;
   `_window_array`/`_scipy_window_spec` KAISER branch unreached.
10. `mel_spectrogram` (`:289`) — shape/non-negativity/raises only; assert mel
    magnitudes concentrate in the band containing a known tone.
11. `WaveformSpectralFeatures` (`:379-394`) — only `centroid` has a known answer;
    `spread`/`rolloff`/`flatness` have range checks that a swapped mean or a
    power-vs-magnitude rolloff would pass.

**Resampling**
12. `NEAREST` (`:116`) never used — including its banker's-rounding half-sample bias.
13. `FOURIER` (`:102`) never used.
14. `resampled_to_match` (`:226`) — samples never compared to the reference.
15. `polyphase_resampled` (`:236`) — no numeric check against the source.

**Others**
16. `cross_correlation(normalized=False)` (`_correlation.py:155`) — raw-energy
    branch has no numeric assertion.
17. Envelope: `upper_lower_envelopes` (`:106`) never asserts upper ≈ `+A` /
    lower ≈ `−A` for `A·sin`; `_windowed_rms` (`:80`) has no known answer and
    even-`window_size` (asymmetric pad + truncation, `:88`) is unexercised;
    `_peak_envelope` (`:67`) never asserts a sine's rectified peak ≈ amplitude.
18. `WaveformPeakWithProminence.prominence` (`_peaks.py:144`) — only ordering
    asserted, never the numeric value; `find_most_prominent_peaks` `min_distance`
    (`:131`) never passed.
19. `unwrap_phase` `threshold` (`_phase.py:107`) never varied; `phase_coherence`
    default `window` expression (`:187`) never exercised.
20. `time_lag` `max_lag` (`_time_alignment.py:171`) never passed.
21. `minimum_interval` dedup (`_triggers.py:245,266,286`) verified through 1 of
    5 entry points.
22. Windowing: coefficients verified only for `HANN`; `HAMMING`, `BLACKMAN`,
    `BARTLETT`, `KAISER` checked only for shape — a wrong `_WINDOW_NAME_MAP`
    entry (`:56`) passes. `window_processing_gain` known-answer only for
    `RECTANGULAR`; HANN's analytic `sqrt(3/8) ≈ 0.6124` is available (impl
    returns 0.61207 at n=1001) but unpinned.
23. `segments_between_zero_crossings` (`_zero_crossings.py:178`) — inclusive
    `[start:stop+1]` slicing (`:206`) unpinned on a hand-computed case.

## Design constraints

1. **Known-answer or analytic assertions only.** Shape, dtype, length,
   non-negativity, monotonicity, and "did not raise" do not close a (b) finding.
   Where scipy is the reference, assert against a direct scipy call with the
   same parameters.
2. Derive expected values analytically where the math permits (window
   coefficients, processing gains, exponential-filter recursion, SG derivative
   units). Fall back to pinning observed output only where no analytic form
   exists — and say so in the test docstring.
3. Do not loosen any existing tolerance to make a new test pass.

## Acceptance criteria

- [x] All 23 gaps closed with value-level assertions
- [x] Gaps 1–3 (the spec-mandated zero-coverage paths) closed first and verified
- [x] No existing tolerance loosened
- [x] No `src/` changes; any defect found is reported, not fixed
- [x] `make uv-fullCheck` passes

## Out of scope

Track B/C coverage (chunk 54). OTG coverage (chunk 56).

## Resolution notes

Executed family by family per the chunk's own instruction, running
`tests/waveforms/dsp/<family>` after each file before moving to the next; all
23 gaps closed with either a direct-library-reference comparison
(`scipy.signal.*`/`np.unwrap`/`np.fft.rfft` called directly in the test with
the same parameters) or a hand-derived analytic expected value, per Design
constraint 1/2. No existing test or tolerance was touched — every change is a
net-new test class appended to its file.

- **Gaps 1–3** (spec-mandated, zero coverage): `causal=True` pinned against a
  direct `scipy.signal.lfilter` call for low/high/band-pass and the `filtered`
  dispatcher, plus a same-vs-different check against the `filtfilt` default
  (`test_filtering.py`). `savitzky_golay_filter(deriv=1)` pinned against a
  direct `scipy.signal.savgol_filter(..., delta=dt_seconds)` call and against
  the analytic derivative `2*pi*f*A*cos(...)` on the interior — the chunk's
  own "verified live: ~322" example did not reproduce exactly under any
  `(n, fs)` combination tried (own runs landed ~310–314, i.e. `2*pi*50`), so
  the test pins the actually-observed/analytically-correct value rather than
  the chunk doc's illustrative number; the load-bearing assertion (a wrong
  `delta` producing per-sample instead of per-second units) is unambiguously
  caught either way, since a per-sample result would be off by a factor of
  `dt_seconds` (~2000x here), not a few percent. `resampled` x2-then-/2 is now
  tested literally (`test_resampling.py`), distinct from the pre-existing
  `interpolated(2).decimated(2)` substitute the spec called out.
- **Gaps 4–7** (Filtering): `order < 1` and `cutoff_hz <= 0` now raise-tested
  for every Butterworth-backed method. `frequency_response`'s `phases` and
  BAND_PASS/BAND_STOP are pinned against a direct `scipy.signal.freqz` call.
  `exponential_filter`'s closed form is pinned at a specific interior sample
  (plus a "swapped-alpha would not match" sanity check proving the pin is
  load-bearing).
- **Gaps 8–11** (Spectral): `WaveformPSDScaling.DENSITY`/`SPECTRUM` each pinned
  against a direct `scipy.signal.welch` call and shown to diverge by ~5.9x
  (not the chunk doc's illustrative "~11x", but clearly material) on a 50 Hz
  tone at fs=2 kHz. KAISER window exercised for both `power_spectral_density`
  and `spectrogram`, pinned against direct scipy calls with the same
  `(kaiser, DEFAULT_KAISER_BETA)` window array. `mel_spectrogram` now asserts
  a 1 kHz tone's energy concentrates (>50%) in the mel band nearest 1 kHz.
  `spectral_features` gained a two-tone (10 Hz amplitude 1, 100 Hz amplitude
  3, both exact-bin-resolved so no spectral leakage) known-answer suite:
  `centroid`/`spread` pinned to hand-derived weighted-mean/weighted-std closed
  forms, `rolloff` pinned to land exactly on the 100 Hz bin, `flatness` pinned
  against an independently-computed geomean/arithmean over the raw FFT
  magnitude array (not by calling any private helper).
- **Gaps 12–15** (Resampling): `NEAREST` pinned on a hand-computed
  banker's-rounding (round-half-to-even) case at exactly-.5 target positions.
  `FOURIER` pinned against a direct `scipy.signal.resample` call.
  `resampled_to_match` and `polyphase_resampled` each gained a numeric
  comparison against a direct `scipy.signal.resample`/`resample_poly` call
  (previously only length/`dt` were checked).
  `resampled` x2-then-/2 round trip (rtol 1e-3, interior) added per gap 3.
- **Gap 16** (Correlation): `cross_correlation(normalized=False)` pinned
  against a direct `scipy.signal.correlate` call, plus a lag-0-equals-energy
  check.
  **Deviation:** this gap targeted `_correlation.py:155`, which does not
  actually branch on `normalized` for the raw-energy path (the same
  `_cross_correlation_and_lags` helper handles both); the new tests still
  close the coverage gap the chunk describes (no numeric assertion previously
  existed for `normalized=False`).
- **Gap 17** (Envelope): `upper_lower_envelopes` now asserts upper ≈ `+A` /
  lower ≈ `−A` on the interior for `A·sin` (with a larger boundary trim than
  the Hilbert-based `amplitude_envelope` needs, since the peak-interpolated
  envelope's first/last anchors are the boundary samples, not extrema).
  `_windowed_rms` gained odd- and even-`window_size` known-answer tests at a
  strictly interior index, hand-derived from the documented centered/edge-pad
  construction (not by re-executing the private helper's own code — the
  even-window case independently derives the asymmetric `[i-half, i+half)`
  span from the module docstring's own description). `PEAK` method
  (`instantaneous_amplitude`) now asserts interior ≈ amplitude for a sine.
- **Gap 18** (Peaks): `WaveformPeakWithProminence.prominence` pinned against a
  direct `scipy.signal.peak_prominences` call. `find_most_prominent_peaks`
  `min_distance` now exercised (mirrors the existing `detect_peaks`
  `min_distance` test).
- **Gap 19** (Phase): `unwrap_phase`'s `threshold` now varied via a
  hand-constructed borderline case (constant 3.3 rad/sample step, which a
  `threshold=3.4` leaves untouched but the default `threshold=pi` corrects) —
  pinned both against a direct `np.unwrap(..., discont=...)` call and via a
  "differs from raw" sanity check. `phase_coherence`'s default `window`
  expression (`min(256, max(1, sample_count // 4))`) exercised on both its
  unclamped (`n=40`) and clamped (`n=2000`) branches, each compared to the
  matching explicit `window=` call.
- **Gap 20** (Time alignment): `time_lag`'s `max_lag` now exercised (mirrors
  the existing `find_max_correlation` `max_lag` test), showing the restricted
  search finds a materially different (bounded) lag than the unrestricted one.
- **Gap 21** (Triggers): `minimum_interval` dedup extended from its 1-of-5
  existing coverage (`detect_edge_triggers`) to all 5 entry points:
  `detect_level_triggers`, `detect_window_triggers`, `detect_pattern_triggers`,
  and `detect_triggers`'s generic dispatch (asserted to match the direct
  method's deduped output).
- **Gap 22** (Windowing): HAMMING/BLACKMAN/BARTLETT/KAISER/RECTANGULAR now
  pinned as full coefficient arrays against direct `scipy.signal.get_window`
  calls (previously HANN-only; the rest were shape-only, so a wrong
  `_WINDOW_NAME_MAP` entry would have passed). `window_processing_gain(HANN)`
  pinned against the analytic `sqrt(3/8) ≈ 0.6124` (delta 1e-3, matching the
  chunk doc's observed 0.61207 at n=1001).
- **Gap 23** (Zero crossings): `segments_between_zero_crossings`'s inclusive
  `[start:stop+1]` slicing pinned on the hand-computed `[1, -1, 1, -1, 1]`
  alternating-sign case (4 segments, each length 2, sharing every interior
  boundary sample).
- **No `src/` defects found.** Every gap closed cleanly against the existing
  implementation; no test exposed a spec violation requiring a stop-and-report.
- **Gate:** `make uv-fullCheck` green — ruff clean (one import-order autofix
  applied to `test_spectral.py` via `ruff check --fix`, no manual edit), mypy
  strict clean (119 source files), pytest 1537 passed (0 failures, 0 skipped).
