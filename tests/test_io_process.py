"""Loading the fixture experiment, and raw processing against the instrument's spectrum."""
import nmrtrain as nt


def test_load_processed_reads_labels_axis_and_date(aa_zip):
    s = nt.load_processed(aa_zip)
    assert (s.sample, s.acid, s.time, s.nucleus) == ("AA", "K", "1day", "1H")
    assert s.label == "Ala-Ala in 98%, 1 day"
    assert s.ppm[0] > s.ppm[-1]                      # high to low
    assert abs(nt.checks.acid_ppm(s) - 11.433) < 0.01
    assert s.acquired.year == 2023 and 399 < s.sf < 401


def test_instrument_scale_is_kept_never_re_referenced(aa_zip):
    s = nt.load_processed(aa_zip)
    assert abs(nt.peaks.tallest_ppm(s) - 11.5) > 0.03   # it is not moved to a nominal acid value


def test_raw_processing_matches_the_instrument(aa_zip):
    inst = nt.load_processed(aa_zip)
    own = nt.process.process_fid(aa_zip)
    assert nt.checks.check_axis(own).kind == "ok"
    assert nt.peaks.similarity(own, inst) > 0.95
    same = nt.peaks.compare(nt.peaks.pick(own), nt.peaks.pick(inst), tol=0.01)
    assert not same["lost"] and not same["new"]


def test_skipping_the_reverse_mirrors_the_axis(aa_zip):
    naive = nt.process.process_fid(aa_zip, reverse_axis=False, do_baseline=False)
    fb = nt.checks.check_axis(naive)
    assert fb.kind == "trap" and "reversed" in fb.text
    assert abs(nt.peaks.tallest_ppm(naive) - 0.57) < 0.1


def test_zip_slip_is_refused(tmp_path):
    import zipfile
    import pytest
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../../evil/acqus", "x")
    with pytest.raises(OSError):
        nt.io.experiment_dir(str(bad))
