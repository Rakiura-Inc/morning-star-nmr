"""Unpacking and labelling the fixture experiment, read with nmrglue as the notebooks read it."""

import zipfile

import pytest

import nmrtrain as nt

from .helpers import notebook_functions


@pytest.fixture
def read_spectrum():
    return notebook_functions("01")["read_spectrum"]


def test_labelled_spectrum_has_labels_axis_and_date(aa_zip, read_spectrum):
    spectrum = read_spectrum(aa_zip)
    assert (spectrum.sample, spectrum.acid, spectrum.time, spectrum.nucleus) == ("AA", "K", "1day", "1H")
    assert spectrum.label == "Ala-Ala in 98%, 1 day" == nt.io.label_of(aa_zip)
    assert spectrum.ppm[0] > spectrum.ppm[-1]  # high to low
    assert abs(nt.checks.acid_ppm(spectrum) - 11.433) < 0.01
    assert spectrum.acquired.year == 2023 and 399 < spectrum.spectrometer_mhz < 401


def test_instrument_scale_is_kept_never_re_referenced(aa_zip, read_spectrum):
    spectrum = read_spectrum(aa_zip)
    assert abs(nt.peaks.tallest_ppm(spectrum) - 11.5) > 0.03  # it is not moved to a nominal acid value


def test_zip_slip_is_refused(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../../evil/acqus", "x")
    with pytest.raises(OSError, match="refusing to unpack"):
        nt.io.experiment_folder(str(bad))


def test_recording_order(aa_zip, read_spectrum):
    first = read_spectrum(aa_zip)
    later = first.with_data(first.ppm, first.intensity, acquired=first.acquired.replace(year=2024))
    assert nt.io.by_recording_date([later, first]) == [first, later]
