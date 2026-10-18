"""Peak picking, trap checks and feedback on synthetic spectra."""
import datetime as dt
import re

import pytest

import nmrtrain as nt
from conftest import synthetic

# Made-up spectra (not readings of the real data): a first and a last time point.
AA_1DAY = [(5.30, 0.5), (4.70, 0.5), (2.285, 1.0), (2.267, 1.0), (1.791, 1.0), (1.773, 1.0)]
AA_4MO = [(6.10, 0.06), (6.03, 0.06), (4.72, 0.5), (2.29, 1.0), (2.272, 1.0)]


def test_pick_merges_a_doublet_and_orders_high_to_low():
    pk = nt.peaks.pick(synthetic(AA_1DAY))
    assert [round(p["ppm"], 2) for p in pk] == [5.3, 4.7, 2.28, 1.78]
    assert pk[2]["lines"] == 2


def test_compare_kept_lost_new():
    a, b = nt.peaks.pick(synthetic(AA_1DAY)), nt.peaks.pick(synthetic(AA_4MO))
    c = nt.peaks.compare(a, b)
    assert [round(p, 2) for p in c["lost"]] == [5.3, 1.78]
    assert [round(p, 2) for p in c["new"]] == [6.1, 6.03]


def test_pick_ref_region_ignores_noise_in_a_quiet_window():
    s = synthetic([(170.0, 0.001), (16.0, 1.0)], lo=0, hi=200, acid_ppm=None, nucleus="13C", width=0.2, n=40000)
    assert nt.peaks.pick(s, 160, 185, 0.05, group_ppm=0.5, ref=(5, 200)) == []


def test_axis_check_ok_and_mirrored():
    ok = synthetic(AA_1DAY)
    assert nt.checks.check_axis(ok).kind == "ok"
    mirrored = ok.with_data(ok.ppm, ok.y[::-1])
    fb = nt.checks.check_axis(mirrored)
    assert fb.kind == "trap" and "reversed" in fb.text


def test_axis_window_for_81_percent():
    s = synthetic([(2.6, 1.0)], acid="H", acid_ppm=12.07)
    assert nt.checks.check_axis(s).kind == "ok"


def test_order_trap_by_label_and_by_date():
    a = synthetic(AA_1DAY, time="5week")
    b = synthetic(AA_1DAY, time="8day")
    fb = nt.checks.check_order([a, b])
    assert fb.kind == "trap" and "5 weeks comes before 8 days" in fb.text
    a.time, b.time = "1day", "3day"
    a.acquired, b.acquired = dt.datetime(2023, 7, 25), dt.datetime(2023, 7, 21)
    assert nt.checks.check_order([a, b]).kind == "trap"


def test_drift_trap():
    s1, s2 = synthetic(AA_1DAY, acid_ppm=11.08), synthetic(AA_1DAY, acid_ppm=11.46, time="1week")
    fb = nt.checks.check_drift([s1, s2])
    assert fb.kind == "trap" and "0.38" in fb.text
    assert nt.checks.check_drift([synthetic(AA_1DAY), synthetic(AA_1DAY, acid_ppm=11.50)]).kind == "ok"


def test_normalisation_trap():
    assert nt.checks.check_normalisation(None).kind == "trap"
    assert nt.checks.check_normalisation((0, 13)).kind == "trap"
    assert nt.checks.check_normalisation((1.0, 6.5)).kind == "ok"


def test_broad_early_note():
    early = synthetic(AA_1DAY, width=0.012)
    later = [synthetic(AA_1DAY, time=t) for t in ("3day", "8day")]
    assert nt.checks.check_broad_early([early] + later).kind == "note"


def test_signal_loss_without_new_peaks_suggests_precipitation():
    first = synthetic(AA_1DAY)
    gone = synthetic([(p, h * 0.2) for p, h in AA_1DAY], time="4Month")
    assert nt.checks.check_signal_loss(first, gone).kind == "trap"
    assert nt.checks.check_signal_loss(first, synthetic(AA_4MO)).kind == "ok"


KEY = nt.answers.load("capstone", quiet=True)

# A synthetic key case (made-up molecule and shifts), so the signal-level feedback is tested without
# shipping any reading of the real spectra.
SYNTH = {"sample": "XX", "acid": "K", "call": "degrades", "call_source": "a test source", "tolerance_ppm": 0.05,
         "signals": [{"ppm": 3.10, "group": "lost", "what": "a test methyl",
                      "if_listed_as": {"kept": "the 3.10 test methyl is the one that goes."}},
                     {"ppm": 4.20, "group": "new", "what": "a new test peak"},
                     {"ppm": 2.50, "group": "kept", "what": "a kept test peak", "backbone": True},
                     {"ppm": 6.00, "group": "new", "what": "a small test peak", "optional": True}],
         "expect": {"1day": {"present": [3.10, 2.50], "absent": []},
                    "4Month": {"present": [4.20, 2.50], "absent": [3.10]}}}
DIPEPTIDE_TABLES = "Check your decision against Table 1 (81%) and Table 2 (98%) of the paper"
GRADING = re.compile(r"\b(correct|incorrect|wrong|score|points|grade)\b|\d%", re.I)


def test_unsure_is_always_a_fair_answer():
    rep = nt.checks.check_verdict({"call": "unsure"}, nt.answers.case(KEY, "AA"))
    assert rep[0].kind == "open" and "fair answer" in rep[0].text


def test_published_call_is_compared_with_its_source():
    agree = nt.checks.check_verdict({"call": "degrades"}, nt.answers.case(KEY, "AA"))
    assert agree[0].kind == "agrees" and "Petkowski et al. 2024" in agree[0].text
    differ = nt.checks.check_verdict({"call": "survives"}, nt.answers.case(KEY, "AA"))
    assert differ[0].kind == "look again" and "Petkowski et al. 2024" in differ[0].text


def test_slips_get_targeted_feedback():
    rep = nt.checks.check_verdict({"call": "degrades", "lost_ppm": [11.43, 7.0], "new_ppm": [7.80], "kept_ppm": [3.10]},
                                  SYNTH, sample="XX")
    text = "\n".join(map(str, rep))
    assert "acid's own signal" in text
    assert "mirror image 4.20" in text
    assert "3.10 test methyl is the one that goes" in text
    assert "swap with the acid's deuterium" in text
    assert "You could also cite 4.20 as new" in text and "6.00" not in text


def test_cited_values_with_no_key_signals_are_left_for_the_reviewer():
    rep = nt.checks.check_verdict({"call": "degrades", "lost_ppm": [11.43, 2.0], "new_ppm": [5.0]},
                                  nt.answers.case(KEY, "AA"))
    text = "\n".join(map(str, rep))
    assert "acid's own signal" in text
    assert "no signal in the key" not in text and "could also cite" not in text


def test_peak_list_check_on_a_synthetic_key():
    mine = {"1day": [{"ppm": 3.11}, {"ppm": 2.50}], "4Month": [{"ppm": 2.49}, {"ppm": 3.10}]}
    rep = nt.checks.check_peak_list(mine, SYNTH)
    kinds = [f.kind for f in rep]
    assert kinds[0] == "agrees"
    assert any("no peak near 4.20" in f.text for f in rep) and any("3.10 should be gone" in f.text for f in rep)


def test_feedback_never_grades():
    cases = [nt.answers.case(KEY, "AA"), SYNTH,
             nt.answers.case(nt.answers.load("dipeptides", quiet=True), "LL-H"),
             nt.answers.case(nt.answers.load("amino_acids", quiet=True), "ASN-H")]
    verdicts = [{"call": c, "lost_ppm": [1.0, 3.10], "product_guess": "x", "confidence": "high"}
                for c in ("survives", "degrades", "unsure", "")]
    for case in cases:
        for v in verdicts:
            for f in nt.checks.check_verdict(v, case):
                assert not GRADING.search(f.text.replace("(81%)", "").replace("(98%)", "")), f.text


def test_prediction_feedback_mentions_water():
    rep = nt.checks.check_prediction({"AA_methyl_ppm": 1.3}, {"AA_methyl_ppm": KEY["prediction"]["AA_methyl_ppm"]})
    assert rep[0].kind == "look again" and "water" in rep[0].text


def test_prediction_is_judged_on_typical_ranges_not_on_this_dataset():
    # The founder's run: a prediction is made before the spectrum is seen, so the feedback gives the
    # typical position taught above and sends the member to the spectrum, never this dataset's range.
    pred = {"AA_signals": 1, "AA_methyl_ppm": 2.0, "AA_alpha_ppm": 3.0, "GG_signals": 4, "GG_ch2_ppm": 5.0,
            "breaks_down": "Gly-Gly"}
    rep = nt.checks.check_prediction(pred, KEY["prediction"])
    text = "\n".join(map(str, rep))
    assert "[" not in text and "residue" not in text and "alpha-H" not in text
    assert "Look again. Ala-Ala signals from hydrogens on carbon: you said 1; the structure gives 4." in text
    assert "start of the chain" in text and "Open hint 2 above" in text
    alpha = str(rep[2])
    assert alpha.startswith("Look again.") and "near 5 ppm" in alpha and "find where it really sits" in alpha
    assert "4.8" not in text and "5.3" not in text
    assert str(rep[1]).startswith("Yes.") and rep[5].kind == "open"


def test_reading_after_the_plot_uses_this_dataset():
    rep = nt.checks.check_reading({"AA_alpha_ppm": 4.92, "AA_methyl_ppm": 3.0}, KEY["reading"], {"AA_alpha_ppm": 3.0})
    assert rep[0].kind == "look again" and "1.9 to 2.2" in rep[0].text
    assert rep[1].kind == "agrees" and "4.8 to 5.3" in rep[1].text and "You predicted 3.0" in rep[1].text
    assert rep[2].kind == "to do"


def test_plain_call_words_are_accepted():
    case = nt.answers.case(KEY, "AA")
    assert nt.checks.check_verdict({"call": "breaks down"}, case)[0].kind == "agrees"
    assert nt.checks.check_verdict({"call": "degrades"}, case)[0].kind == "agrees"
    assert "'breaks down'" in nt.checks.check_verdict({"call": "survives"}, case)[0].text
    assert nt.checks.verdict_problems({"AA": {"call": "side chain changed"}}, ["AA"]) == []
    row = nt.record.replication_row("LL", "K", {"call": "breaks down"}, ["1day", "4Month"])
    assert row["verdict"] == "degrades"


def test_format_messages_are_friendly_and_never_block():
    probs = nt.checks.verdict_problems({"AA": {"call": "broken", "lost_ppm": ["2.0"]}}, ["AA"], {"AA": "Ala-Ala"})
    assert probs[0].startswith('The decision for Ala-Ala is "broken": write one of "survives", "breaks down"')
    assert "without quotes" in probs[1]
    notes = nt.checks.verdict_notes({"AA": {"call": "", "lost_ppm": [], "kept_ppm": [2.0]}}, ["AA"], {"AA": "Ala-Ala"})
    assert notes == ['Ala-Ala: still empty: decision, lost peaks. An empty peak list is fine if there were none, '
                     'and "unsure" is a fair answer.']


def test_write_down_confirms_by_name(capsys):
    nt.record.write_down("AA_LOST_PPM", [2.08, 4.94], "Ala-Ala", "lost_ppm", suggestion=[5.17, 2.08])
    out = capsys.readouterr().out
    assert out.startswith("Saved AA_LOST_PPM = [2.08, 4.94]: 2 lost peaks for Ala-Ala, at 2.08 and 4.94 ppm.")
    assert "also listed 5.17" in out
    nt.record.write_down("AA_LOST_PPM", [], "Ala-Ala", "lost_ppm", suggestion=[5.17])
    assert "Copy the ones you agree with" in capsys.readouterr().out
    nt.record.write_down("AA_CALL", "", "Ala-Ala", "call")
    assert capsys.readouterr().out.startswith("Not saved yet AA_CALL = ''")
    nt.record.write_down("AA_CALL", "breaks down", "Ala-Ala", "call")
    assert capsys.readouterr().out.startswith("Saved AA_CALL = 'breaks down'")


def test_build_verdict_keeps_the_hand_in_format(capsys):
    v = nt.record.build_verdict({"AA": {"call": "unsure", "lost_ppm": [1.99]}}, names={"AA": "Ala-Ala"},
                                examples={"Gly-Gly (example)": {"call": "survives"}}, note="n")
    assert v == {"AA": {"call": "unsure", "lost_ppm": [1.99]}, "note": "n"}
    out = capsys.readouterr().out
    assert "| **Gly-Gly (example)** | survives |" in out and "| **Ala-Ala** | unsure | 1.99 |" in out


def test_backbone_check():
    assert nt.checks.check_backbone(2.50, SYNTH).kind == "agrees"
    assert nt.checks.check_backbone(3.10, SYNTH).kind == "look again"
    assert nt.checks.check_backbone(..., SYNTH).kind == "to do"
    keyless = nt.checks.check_backbone(5.0)
    assert keyless.kind == "open" and "reviewer" in keyless.text


@pytest.mark.parametrize("name", nt.answers.available())
def test_every_key_holds_published_calls_only(name):
    key = nt.answers.load(name, quiet=True)
    assert key["status"] == "published calls only" and key["cases"]
    for cid, case in key["cases"].items():
        assert case["call"] in nt.checks.KEY_CALLS and case["call"] != "unsure", cid
        assert re.search(r"et al\. 20\d\d", case["call_source"]), cid
        if "product" in case:
            assert re.search(r"et al\.", case["product_source"]), cid
        for own in ("signals", "expect", "why", "data_reading", "changes_seen", "backbone", "reference"):
            assert own not in case, (cid, own)


def test_only_ala_ala_and_gly_gly_in_98_percent_are_keyed():
    assert nt.answers.available() == ["c13_series", "capstone", "dipeptides"]
    for name in nt.answers.available():
        key = nt.answers.load(name, quiet=True)
        assert {(c["sample"], c["acid"]) for c in key["cases"].values()} == {("AA", "K"), ("GG", "K")}, name
    key = nt.answers.load("dipeptides", quiet=True)
    assert key["cases"]["AA-K"]["call"] == "degrades" and key["cases"]["GG-K"]["call"] == "survives"


def test_a_case_with_no_key_points_to_the_paper_tables(capsys):
    key = nt.answers.load("dipeptides", quiet=True)
    for v in ({"call": "degrades"}, {"call": "unsure"}):
        rep = nt.checks.check_verdict(v, nt.answers.case(key, "LL-H"))
        assert rep[0].kind == "open" and DIPEPTIDE_TABLES in rep[0].text
    amino = nt.answers.load("amino_acids")
    assert "Table 1 of the paper (M. D. Seager et al. 2024, Astrobiology 24, 386)" in capsys.readouterr().out
    rep = nt.checks.check_verdict({"call": "side chain modified", "product_guess": "x"}, nt.answers.case(amino, "ASN-H"))
    assert "Astrobiology 24, 386" in rep[0].text and rep[0].kind == "open"
    assert all(f.kind in ("open", "to do", "note") for f in rep)


def test_how_much_is_left_is_measured_against_the_acid_peak():
    first = synthetic(AA_1DAY)
    half = synthetic([(p, h * 0.5) for p, h in AA_1DAY], time="8day")
    gone = synthetic([(p, h * 0.1) for p, h in AA_1DAY], time="4Month")
    left = nt.peaks.left_of_first([first, half, gone], (1.75, 1.81))
    assert left[0] == 1.0 and abs(left[1] - 0.5) < 0.02 and abs(left[2] - 0.1) < 0.02
    assert [nt.peaks.left_band(x) for x in (1.5, 1.0, 0.5, 0.34, 0.33, 0.0)] == [
        "no clear loss", "no clear loss", "no clear loss", "no clear loss", "little or none", "little or none"]
    assert nt.checks.LEFT == ("little or none", "no clear loss", "unsure")


def test_survival_compares_the_molecules_own_peaks():
    first = synthetic(AA_1DAY)
    # The whole molecule halves (both alphas together): its own peaks keep their sizes relative to each other.
    both = synthetic([(p, h * 0.5) for p, h in AA_1DAY], time="8day")
    # Only the alpha near 5.30 ppm falls: the ratio to the other alpha falls with it.
    one = synthetic([(p, h * (0.2 if p > 5 else 1.0)) for p, h in AA_1DAY], time="4Month")
    own = nt.peaks.against_own_peak([first, both, one], (5.25, 5.35), (4.65, 4.75))
    assert own[0] == 1.0 and abs(own[1] - 1.0) < 0.02 and abs(own[2] - 0.2) < 0.02
    assert abs(nt.peaks.second_peak_ppm(first, 1.0, 6.5, away_from=2.28) - 1.78) < 0.03


def test_line_differences_find_the_largest_shift():
    inst = synthetic(AA_1DAY)
    mine = synthetic([(p + (0.004 if p > 5 else 0.0), h) for p, h in AA_1DAY])
    d = nt.peaks.line_differences(mine, inst)
    assert abs(d["largest_ppm"] - 0.004) < 0.001 and abs(d["at_ppm"] - 5.30) < 0.002 and d["lines"] == 6
    assert nt.checks.line_feedback(d).kind == "agrees"
    far = nt.peaks.line_differences(synthetic([(p + 0.05, h) for p, h in AA_1DAY]), inst)
    assert nt.checks.line_feedback(far).kind == "look again"
