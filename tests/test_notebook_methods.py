"""The analysis the notebooks teach in their own cells: run against the package's copies (which the
trap checks use) and against the instrument's own processing."""

import pytest

import nmrtrain as nt

from .helpers import notebook_functions, synthetic

# Made-up spectra (not readings of the real data): a first and a last time point.
AA_1DAY = [(5.30, 0.5), (4.70, 0.5), (2.285, 1.0), (2.267, 1.0), (1.791, 1.0), (1.773, 1.0)]
AA_4MO = [(6.10, 0.06), (6.03, 0.06), (4.72, 0.5), (2.29, 1.0), (2.272, 1.0)]


@pytest.fixture(scope="module")
def nb01():
    return notebook_functions("01")


@pytest.fixture(scope="module")
def nb04():
    return notebook_functions("04")


@pytest.mark.parametrize("name", ["01", "02", "03", "04", "05"])
def test_every_notebook_picks_peaks_as_the_trap_checks_do(name, aa_zip):
    """The notebooks' pick_peaks and the package's copy stay the same (change both, or neither)."""
    functions = notebook_functions(name)
    spectra = [synthetic(AA_1DAY), synthetic(AA_4MO), functions["read_spectrum"](aa_zip)]
    for spectrum in spectra:
        assert functions["pick_peaks"](spectrum, (1.0, 6.5), min_height=0.03) == nt.peaks.pick(spectrum)


def test_pick_merges_a_doublet_and_orders_high_to_low(nb01):
    peaks = nb01["pick_peaks"](synthetic(AA_1DAY), (1.0, 6.5), min_height=0.03)
    assert [round(peak["ppm"], 2) for peak in peaks] == [5.3, 4.7, 2.28, 1.78]
    assert peaks[2]["lines"] == 2


def test_compare_kept_lost_new(nb01):
    first = [peak["ppm"] for peak in nb01["pick_peaks"](synthetic(AA_1DAY), (1.0, 6.5), 0.03)]
    last = [peak["ppm"] for peak in nb01["pick_peaks"](synthetic(AA_4MO), (1.0, 6.5), 0.03)]
    changes = nb01["compare_peaks"](first, last)
    assert changes == nt.peaks.compare(first, last)
    assert [round(ppm, 2) for ppm in changes["lost"]] == [5.3, 1.78]
    assert [round(ppm, 2) for ppm in changes["new"]] == [6.1, 6.03]


def test_peak_width_matches_the_trap_check(nb01):
    broad = synthetic(AA_1DAY, width=0.012)
    peak_ppm, width_hz = nb01["peak_width_hz"](broad, near_ppm=2.28)
    assert width_hz == nt.peaks.linewidth_hz(broad, 2.28) and abs(peak_ppm - 2.28) < 0.02


def test_how_much_is_left_is_measured_against_the_acid_peak(nb01):
    first = synthetic(AA_1DAY)
    half = synthetic([(ppm, height * 0.5) for ppm, height in AA_1DAY], time="8day")
    gone = synthetic([(ppm, height * 0.1) for ppm, height in AA_1DAY], time="4Month")
    ratios = nb01["area_ratios"]([first, half, gone], (1.75, 1.81), nb01["ACID_PEAK_PPM"])
    left = nb01["share_of_first"](ratios)
    assert left[0] == 1.0 and abs(left[1] - 0.5) < 0.02 and abs(left[2] - 0.1) < 0.02
    levels = [nb01["how_much_is_left"](share) for share in (1.5, 1.0, 0.5, 0.34, 0.33, 0.0)]
    assert levels == ["no clear loss"] * 4 + ["little or none"] * 2
    assert nt.checks.LEFT == ("little or none", "no clear loss", "unsure")


def test_survival_compares_the_molecules_own_peaks():
    nb02 = notebook_functions("02")
    first = synthetic(AA_1DAY)
    # The whole molecule halves (both alphas together): its own peaks keep their sizes relative to each other.
    both = synthetic([(ppm, height * 0.5) for ppm, height in AA_1DAY], time="8day")
    # Only the alpha near 5.30 ppm falls: the ratio to the other alpha falls with it.
    one = synthetic([(ppm, height * (0.2 if ppm > 5 else 1.0)) for ppm, height in AA_1DAY], time="4Month")
    followed = nb02["follow_peak"]([first, both, one], peak_ppm=5.30, other_ppm=4.70)
    own = followed["own"]
    assert own[0] == 1.0 and abs(own[1] - 1.0) < 0.02 and abs(own[2] - 0.2) < 0.02
    assert abs(nb02["next_tallest_ppm"](first, (1.0, 6.5), away_from_ppm=2.28) - 1.78) < 0.03
    assert nb02["share_of_first"]([0.0, 0.5]) == [0.0, 0.0]  # a chosen peak missing at the first time point


def test_carbon_picking_ignores_noise_in_a_quiet_window():
    nb05 = notebook_functions("05")
    spectrum = synthetic([(170.0, 0.001), (16.0, 1.0)], lo=0, hi=200, acid_ppm=None, nucleus="13C", width=0.2, n=40000)
    found = nb05["pick_peaks"](spectrum, (160, 185), min_height=0.05, group_ppm=0.5, scale_region=(5, 200))
    assert found == []


def test_raw_processing_matches_the_instrument(aa_zip, nb04):
    instrument = nb04["read_spectrum"](aa_zip)
    mine = nb04["process_fid"](aa_zip, zero_fill=65536)
    assert nt.checks.check_axis(mine).kind == "ok"
    assert nb04["similarity"](mine, instrument) > 0.95
    differences = nb04["largest_line_difference"](mine, instrument)
    assert differences["largest_ppm"] < 0.01 and differences["lines"] >= 4
    assert nt.checks.line_feedback(differences).kind == "agrees"


def test_skipping_the_reverse_mirrors_the_axis(aa_zip, nb04):
    mine = nb04["process_fid"](aa_zip, zero_fill=65536)
    mirrored = mine.with_data(mine.ppm, mine.intensity[::-1])
    feedback = nt.checks.check_axis(mirrored)
    assert feedback.kind == "trap" and "reversed" in feedback.text
    assert abs(nt.peaks.tallest_ppm(mirrored) - 0.57) < 0.1


def test_a_zero_fill_smaller_than_the_recording_does_not_crash(aa_zip, nb04, capsys):
    mine = nb04["process_fid"](aa_zip, zero_fill=8192)
    assert "nothing to pad" in capsys.readouterr().out
    assert mine.intensity.size >= 32768 - 200


def test_line_differences_find_the_largest_shift(nb04):
    instrument = synthetic(AA_1DAY)
    mine = synthetic([(ppm + (0.004 if ppm > 5 else 0.0), height) for ppm, height in AA_1DAY])
    differences = nb04["largest_line_difference"](mine, instrument)
    assert abs(differences["largest_ppm"] - 0.004) < 0.001 and abs(differences["at_ppm"] - 5.30) < 0.002
    assert differences["lines"] == 6
    far = nb04["largest_line_difference"](synthetic([(ppm + 0.05, h) for ppm, h in AA_1DAY]), instrument)
    assert nt.checks.line_feedback(far).kind == "look again"
