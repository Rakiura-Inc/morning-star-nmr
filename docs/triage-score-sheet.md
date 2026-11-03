# The triage score sheet

For the Morning Star Missions Bootcamp step "Could your gas be a sign of life? Run it through the
three tests yourself", and the Extra on the lab's list of small molecules. The lecture video and
the table of scored gases are on the step page.

## Why three tests

A telescope detects a gas in a planet's atmosphere by the light it absorbs. Each gas absorbs its own
pattern of wavelengths (its spectrum); one dip in that pattern is a spectral feature. Where two gases
absorb at the same wavelength, that feature alone cannot tell you which gas is there. You need a
feature that only your gas has.

About 14,000 small molecules (stable, volatile, with up to six atoms other than hydrogen) could exist
as gases, too many to study one by one. The lab sorts them first. Every candidate faces three tests:

1. Can a telescope see it, and tell it apart from the gases around it?
2. Could life make enough of it to build up?
3. Can a planet without life make it too? If so, detecting it could be a false positive: a sign of
   life with no life behind it.

A strong sign of life passes all three. In practice no gas passes all three cleanly, so a plain pass
or fail tells you little. What tells you most is which test a gas fails first, and how badly. Take
the tests in order, 1 to 3: a gas a telescope cannot see is dropped at once, so the other two tests
are not worth running for it.

Two gases from the lecture:
- **Isoprene.** Life on Earth makes about as much isoprene as methane, and nothing without life is
  known to make it. It still fails test 2: Earth's air destroys it within hours, and to build up to a
  level a telescope could see, life would have to make it about a hundred times faster than life on
  Earth does.
- **Phosphine.** It has distinct spectral features, and on Earth it is linked with life. It passes
  test 2 only under a condition: it builds up only if life makes a lot of it, so the table puts its
  tick for production in brackets. The table gives phosphine a tick on test 3, but whether a planet
  without life, through volcanoes for example, could also make it is still debated; that is the
  Extra on the phosphine debate.

To see this for yourself, open the free PhET simulation [Molecules and Light](https://phet.colorado.edu/en/simulations/molecules-and-light)
in your browser, choose infrared light, and switch between molecules to see which ones absorb it.
The hand-in does not need it.

## Test 1: can a telescope see it, and tell it apart?

On the [NIST Chemistry WebBook](https://webbook.nist.gov/chemistry/), search for your gas by name,
tick "IR spectrum" and open it. In the three boxes under the plot, choose normal X, microns and
Absorbance, so the x axis is wavelength in microns. Look for a feature between 1 and 12 microns, the
range the lecture uses for this test. The slides on the step page go through this click by click.

Then compare it with the background gases CO2 and H2O, which absorb across much of the infrared. The
lab's [spectra tool](https://spectra-analyzer-mit-v4.streamlit.app/) draws them on one plot:
- Type any name under "Username" in the sidebar and click "Login".
- Under "Select Foreground Molecules", pick your gas, CO2 and H2O. The list shows each molecule by
  its SMILES code; the table above it gives each code next to the molecule's name. The molecules you
  pick are drawn in colour; every other molecule in the tool is drawn as faint grey shading behind
  them.
- Click "Confirm Selection and Start Plotting".

If the tool does not load, compare the three NIST spectra by eye. Look for at least one feature of
your gas at a wavelength where CO2 and H2O absorb little. That is the feature a telescope could use,
and naming it is what a tick on this test needs.

**Stuck?** If NIST has no infrared spectrum for your gas, pick another gas.

## Test 2: could life make enough of it?

This test asks whether life could make your gas fast enough for it to build up against everything
that destroys it, such as starlight and reactions with other gases. Isoprene fails here: life would
need to make about a hundred times more than life on Earth does.

Look up your gas in the lab's [All Small Molecules database](http://www.allmols.org/ASM4_5.html).
The "Produced by life" column says whether life on Earth is known to make it. Then search
[SciX](https://scixplorer.org/) (the free NASA-funded search engine for space and earth science
papers) for your gas plus "biosignature" (a sign of life). Look for a paper that estimates how fast
life would have to make the gas for it to build up to a level a telescope could detect, and score it:
- Tick: the paper finds that rate reasonable, about what life on Earth makes or less.
- Cross: the paper finds it needs far more than life on Earth makes. Isoprene, at about a hundred
  times, is a cross.
- ?: no paper gives an estimate, or a paper gives one but life on Earth is not known to make the gas,
  so there is no Earth rate to compare it with.

The lecture sets no fixed number between "about" and "far more". Go by the paper's own conclusion,
and write both rates in your note so a reader can judge.

## Test 3: can a dead planet make it?

This test asks whether a planet without life could make enough of your gas to fool a telescope. Here
a yes is bad news, so it scores a cross. The lecture asks it as: does the gas have any significant
false positive sources, for example volcanoes, or does it already occur as an ordinary gas in a
lifeless atmosphere?

Search [SciX](https://scixplorer.org/) for your gas plus "false positive", "volcanic" or "abiotic"
(made without life). Look for sources that need no life: volcanoes, reactions between rock and water,
chemistry driven by starlight. Score it:
- Cross: a paper names a source without life that could make a detectable amount. Oxygen is a cross:
  the Extra on oxygen shows how a dry planet can build it up without life.
- Tick: papers that look for such sources find none that matters. This is the lecture table's "no
  known significant false positives". Phosphine has a tick.
- ?: you found no paper either way. Finding nothing is a "?", not a tick.

**Stuck?** This is the hardest of the three tests. Put "?" and ask about your gas in the lab's
Discord channel.

## Write it down

For each of the three tests: a tick, a cross or a ?, and one line of evidence. Then the first test,
in order 1 to 3, that your gas fails.
