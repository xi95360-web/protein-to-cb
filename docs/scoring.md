# From CB scores to functional conclusions

## Two different meanings of a negative score

`raw_stateN` is the native ProteinMPNN sum of conditional log probabilities. It is normally negative, so its sign alone does not indicate loss of function. `pmpnn_stateN = raw_mutant − raw_WT` measures the change relative to WT on the same backbone. A negative delta means lower model compatibility than WT. It is not a folding free energy, activity measurement, or expression level.

Suppose a mutant changes the score by −1.3 on an apo backbone and −2.6 on a ligand-bound backbone. Compatibility decreases in both states, with a larger decrease in the bound state. The unstandardized difference is +1.3, suggesting a relative preference for this apo backbone. It does not establish increased apo occupancy or translate into a fold change in activity or binding. Raw totals are particularly unsuitable for direct comparison when the backbones cover different numbers of residues.

## Degenerate standardization with WT plus one mutant

The authors' code standardizes each column over the supplied panel using the population standard deviation (`ddof=0`), then subtracts the standardized columns. For columns `[0, −1.3]` and `[0, −2.6]`, both standardized columns become `[+1, −1]`, producing bias values `[0, 0]`. This loss of information follows from the panel composition. It does not demonstrate the absence of a conformational effect. Adding unrelated variants is not a calibration procedure.

An expanded study should define a scientifically justified background panel, reference-state ensemble, and independent validation criteria in advance. Do not run a saturation scan without a request. The current workflow retains native standardization while prioritizing raw and WT-relative values for small panels.

## What the original method predicts

CB takes two or more reference conformations with functional relevance. An inverse-folding model scores variant sequences against each backbone to identify candidates with contrasting compatibility. Its direct target is conformational preference. When a state is linked to a function, the selected variants can be enriched for corresponding functional changes.

Functions examined in the original study include effector binding, basal receptor signaling, enzyme activity, and LplA on-target versus off-target protein labeling. CB does not directly generate new mutant coordinates or predict arbitrary functions, EC50, kcat, Km, conformational percentages, or activation barriers.

## What the authors' assays validated

1. **Retrospective validation against existing mutational scans (Fig. 2 and supplementary figures).** The authors compared groups predicted to favor different states with measured state-related readouts, including K-Ras effector binding, basal β2AR activation, and activity-related measurements for Src and other enzymes. These provide functional associations; most do not directly measure conformational populations in solution.
2. **LplA conformational experiments (Fig. 3).** SEC-SAXS with open/closed mixture fitting assessed solution-state distributions, while tryptophan fluorescence provided a readout of conformational change. The methods offered complementary structural evidence. SAXS population estimates came from fitting, rather than probabilities directly output by CB.
3. **LplA functional experiments (Fig. 4).** Flow cytometry measured promiscuous labeling of endogenous proteins, alongside target-protein labeling, gel analysis, and live-cell imaging to evaluate labeling preference and signal-to-noise ratio. Open-biased candidates were generally more promiscuous; closed-biased candidates generally reduced off-target labeling. Some variants retained similar on-target labeling, so the result should not be reduced to “open means higher total enzyme activity.”
4. **Prediction–experiment comparisons (Fig. 5).** Conformational and functional measurements were compared with CB scores and alternative methods, including single-structure scoring. Enrichment and correlation support screening utility; they do not guarantee an accurate conclusion for every mutant.

For prospective LplA selection, the authors additionally required a score above WT on at least one state before choosing strongly biased groups. This was a study-specific selection criterion, not a universal requirement for CB. An individual mutant scoring below WT on both states should not be presented as equally strong evidence of successful design.

## STING G166E: computational signals versus established experiments

Fixed-backbone single-chain compatibility does not represent STING dimer or polymer interfaces, membrane context, trafficking, or downstream TBK1/IRF3 signaling. The original G166E study reported enhanced IRF3/IFN-β signaling without cGAMP, supporting gain of function. Its proposed dimer-interface mechanism used modeling and docking, rather than an experimentally determined G166E structure.

Consequently, a relative apo signal from the single-chain calculation can coexist with experimental evidence of increased basal activation. This indicates that the current inputs or representation may not capture the relevant functional mechanism; the calculation cannot overturn the experiments. Increased basal signaling also does not automatically imply a lower ligand EC50 or physical activation barrier.

## Sources

- Cavanagh et al., *Science* (2026), [original CB study](https://doi.org/10.1126/science.adv7953), Fig. 1–5, Discussion, and LplA candidate-selection methods. Native computation is implemented in the [authors' repository](https://github.com/alicetinglab/ConformationalBiasing).
- König et al., *Annals of the Rheumatic Diseases* (2017), [Familial chilblain lupus due to a gain-of-function mutation in STING](https://doi.org/10.1136/annrheumdis-2016-209841), Fig. 2; [institutionally archived paper](https://ri.conicet.gov.ar/bitstream/11336/51987/2/CONICET_Digital_Nro.3fb93f0c-62a9-49d8-a1a0-299e017ce48c_A.pdf).
