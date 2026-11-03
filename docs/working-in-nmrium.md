# Working in NMRium

[NMRium](https://www.nmrium.org/) runs in your browser: free, no install. This guide is for the
hydrogen-spectrum steps of the Morning Star Missions Bootcamp and of the project Can Life Survive in
Venus's Clouds?, if you would rather not run the notebooks. What to look for in each spectrum is in
the notebook the step links: read its text in the step page's preview, no need to run it.

## The moves you need

- **Load:** drag a spectrum's zip file onto the grey "Drag and drop here" box. Leave the inner zips
  zipped. Load files one at a time, in time order, and note which colour is which time point:
  dropped in together, the files load in file-name order, not time order. When a file holds both the
  FID and a processed spectrum, NMRium loads the processed one ([loading a spectrum](https://docs.nmrium.org/20_1d-spectra/loading_a_spectrum/)).
- **Stack:** with the mouse over the spectrum, press s to stack them; press s again to lay them back
  on top of each other. The [spectra panel](https://docs.nmrium.org/help/spectraPanel) shows or hides
  each one.
- **Label peaks:** press p for the [peak picking tool](https://docs.nmrium.org/help/peaks), then click
  each peak you want to label. NMRium writes its ppm value next to it. Label the acid peak first,
  while the whole spectrum is in view. The Peaks panel lists each peak's position in ppm, and **Copy
  as TSV** copies the list.
- **Zoom:** [Zoom Mode](https://docs.nmrium.org/help/zoom-and-scale).
- **Measure an area:** the [Ranges tool](https://docs.nmrium.org/help/ranges/) gives each range you
  draw a relative area. In hydrogen NMR that area is proportional to the number of hydrogens behind
  the peak. How to turn areas into "how much is left" is in notebook 02, under How much is left.
- **Save a picture:** click the Export button on the left of the spectrum and choose Export as PNG.
- **Leave the ppm scale** as each file came, except where a section below says otherwise.

**Stuck?** If the acid peak shows near 0 to 0.6 ppm instead of near 11.5 (98% acid) or 11.7 to 12.1
(81% acid), the spectrum is mirrored: its ppm scale runs the wrong way. If that happens, or the
files will not load, post a screenshot in the lab's Discord channel.

## Bootcamp: alanine over a month

Download **Suppl. Dataset S1 AA 1D NMR.zip** (about 275 MB) from [the lab's amino-acid data](https://zenodo.org/records/8381013).
In this name, AA means amino acids and 1D means ordinary spectra with one ppm axis. Unzip it. Inside,
each spectrum is its own smaller .zip file. You need these three alanine hydrogen files:
- 1 day: SZSSea-ALA-D2SO4lock-1H-04112023_1 (1).zip, in the folder "aa 1H 98 1day original data"
- 8 days: SZSSea-ALA-8day-D2SO4lock-1H-04182023_1.zip, in "aa 1H 98 1week original data". The folder
  says 1 week; the file name gives the real time point, 8 days.
- 1 month: SZSSea-ALA-1month-D2SO4lock-1H-05102023_1.zip, in "aa 1H and 13C 98 1month original data"

What to look at: notebook 01, Part 1. Hand in two pictures of the stack (the whole spectrum with the
acid peak labelled, and 1 to 7 ppm with alanine's peaks labelled), your call and the peaks in ppm
that support it.

## Bootcamp: Ala-Ala over four months

From [Zenodo 11223995](https://zenodo.org/records/11223995), download "Suplementary dataset S1.zip"
(about 190 MB) and unzip it. Each spectrum inside is its own .zip file; leave those zipped. In file
names such as SZSSea-AA-K-1day-1H, AA stands for Ala-Ala (not amino acids, as in the alanine data),
GG for Gly-Gly and K for 98% acid. Use the 1H (hydrogen) files of Ala-Ala at 1day, 3day, 8day, 5week
and 4Month. If you load them all at once, they sort as 1day, 3day, 4Month, 5week, 8day, which is not
time order. The Gly-Gly files (GG-K) are optional. Zoom to 1 to 6.5 ppm.

The second candidate product: from [Zenodo 11122291](https://zenodo.org/records/11122291), download
"SUPPLEMENTARY DATASETS 1-5.zip" (about 100 MB) and open SZSSea-LAlaninamide-1H-06072024_1.zip in its
Dataset S4 folder.

What to look at: notebook 01, Parts 2 to 5. Hand in Ala-Ala's 1 day and 4 month spectra, stacked,
with the peaks labelled in ppm, and a note: your decision and the peaks that support it, in ppm;
what you think the main product is, and why; how sure you are.

## Project: one dipeptide at two acid strengths

Same "Suplementary dataset S1.zip". Pick one homodipeptide (two copies of the same amino acid):

| Dipeptide | Code | Dipeptide | Code |
|---|---|---|---|
| Arg-Arg | RR | Leu-Leu | LL |
| Asn-Asn | NN | Lys-Lys | KK |
| Asp-Asp | DD | Met-Met | MM |
| Cys-Cys | CC | Phe-Phe | FF |
| Gln-Gln | QQ | Pro-Pro | PP |
| Glu-Glu | EE | Ser-Ser | SS |
| His-His | HH | Thr-Thr | TT |
| Ile-Ile | II | Trp-Trp | WW |
| Tyr-Tyr | YY | Val-Val | VV |

After the SZSSea prefix, each file name has four parts, then the recording date. In
SZSSea-VV-K-1day-1H:
- VV is the dipeptide, Val-Val
- K is the acid strength: K means 98% acid and H means 81% acid
- 1day is the time in the acid: 1day, 3day, 8day, 5week or 4Month
- 1H means a hydrogen spectrum; 13C files are carbon spectra

The acid letter comes after the dipeptide code, so in SZSSea-KK-H-1day-1H the KK is Lys-Lys and the
H is 81% acid.

**Stuck?** Gln-Gln (QQ) has no 98% four-month file: use 5 weeks, or pick another. His-His's
four-month files end in "4MonthR".

What to look at, and how to measure how much is left: notebook 02. Hand in:
- Your two stacked spectra, one per acid, with the acid peak and your dipeptide's peaks labelled
- For each acid, your decision and the first time point where you saw a change
- The peaks that support each decision, in ppm
- How much is left at four months in each acid (little or none, or no clear loss), with the day 1
  value and the four-month value you divided (each is your peak's area over the acid peak's)
- The main product, if you can name it. Compare the new peaks with the single amino acid's own
  spectrum in the same acid, from the amino acid data above ([Zenodo 8381013](https://zenodo.org/records/8381013)).
  If they match, name it. If they do not, write "not the single amino acid" and give the new peaks'
  positions.
- How sure you are

## Project: asparagine

From the amino acid data ([Zenodo 8381013](https://zenodo.org/records/8381013)), "Suppl. Dataset S1
AA 1D NMR.zip". Folder names give the nucleus (1H for hydrogen, 13C for carbon), the acid strength
and the time. File names give the amino acid: ASN is asparagine and ASP is aspartic acid. Stack
asparagine in 98% acid at 1 day, 1 week and 1 month; the file in the 1week folder is named 9day: it
was measured at 9 days. The carbon file is SZSSea-ASN-1month-D2SO4lock-13C-05102023_1.zip, in the
folder "aa 1H and 13C 98 1month original data".

What to look at, and how to count carbon peaks: notebook 03, Parts 2 and 3. Hand in:
- Your stacked asparagine spectra in 98% acid (1 day, 1 week and 1 month), with the alpha, side-chain
  CH2 and NH3+ peaks labelled
- Your decision, and the peaks that support it, in ppm
- How many large peaks the 1 month carbon spectrum shows, and where
- How the 98% result differs from the 81% worked case

## Project Extra: carbon spectra of Ala-Ala

Load Ala-Ala's 98% 13C files at 1day and 4Month from "Suplementary dataset S1.zip" and count the
large peaks between 170 and 180 ppm. What to look at: notebook 05. Hand in the two carbon spectra
with the carbonyl peaks labelled, how many large carbonyl peaks you count at 1 day and at 4 months,
what that says about how Ala-Ala broke apart, and which bond the mechanism paper says breaks.

## Project Extra: Gly-Gly's 4.77 ppm peak

Load the Gly-Gly 98% files (GG-K, 1day to 4Month) and zoom in on its two CH2 peaks, near 4.6 and 4.8
ppm. Hand in your zoomed spectra, the possible causes you listed and the evidence that would tell
them apart, the cause you favour and why, and how sure you are.

## Project Extra: serine and O-sulfoserine

From the amino acid data, three serine (SER) files in 98% acid:
- 1 day: SZSSea-SER-D2SOlock-1H-04042023_1 (1).zip, in the folder "aa 1H 98 1day original data"
- 8 days: SZSSea-SER-8day-D2SO4lock-1H-04102023_1.zip, in "aa 1H 98 1week original data"
- 1 month: SZSSea-SER-1month-D2SO4lock-1H-05102023_1.zip, in "aa 1H and 13C 98 1month original data"

Stack the 8 day and 1 month files and leave their ppm scales alone. The 1 day file needs one
correction. Its ppm scale was set differently when it was recorded: its acid peak sits at about
11.08 ppm, not near 11.5, and every peak in it sits about 0.38 ppm lower than in the 8 day file (4.59
matches 4.97, and 6.83 matches 7.22). Pick its peaks, then add 0.38 to each position before you
compare it with the other files.

Load O-sulfoserine measured in the same acid: file SZSSea-OSulfLSer-K-1Day-1H, in the folder
"sulfSer-oxMet-oxCys-sulfCys 1H and 13C 98 1day original data". Lay it over your serine stack. Compare
the peaks from hydrogens on carbon, between 4.8 and 5.3 ppm, and write down each peak's position in
serine and in O-sulfoserine.

What to look at, and the four calls: notebook 03, Part 5. Hand in your stacked serine spectra with
O-sulfoserine laid over them, your decision, and the peak positions in serine and in O-sulfoserine
that support it, in ppm, with 0.38 added to the 1 day positions.

## Raw data

NMRium shows the instrument's processed spectrum, not your own processing. To process the raw signal
(the FID) you need Python: notebook 04. NMRium is still useful there, to pick the instrument
spectrum's lines and copy them as TSV.
