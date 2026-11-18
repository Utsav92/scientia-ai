"""WEAK SUPERVISION: keyword-lexicon domain labels.

peS2o v2 records carry no field-of-study label. These labels are noisy heuristics used for
(a) stratified sampling during ingestion and (b) training the domain classifier. Any metric measured
against them measures agreement with this heuristic, NOT true domain accuracy. The README states this.
"""
from __future__ import annotations
import re

LEXICON = {
    "physics": r"quantum|photon|boson|fermion|lattice|superconduct|spin|magnetic field|relativity|cosmolog|dark matter|plasma|particle physics|hamiltonian|entanglement|thermodynamic|condensed matter|laser|optical|astrophys|gravitational|neutrino|topological insulator",
    "chemistry": r"synthesis of|catalys|molecular|solvent|reaction|polymer|ligand|spectroscop|nanoparticle|electrochem|organic compound|oxidation|crystal structure|chemical|adsorption|ionic|density functional|covalent|nmr|perovskite",
    "biology": r"protein|gene |genes|genom|cell |cells |rna|dna|enzyme|species|patients|clinical|disease|mice|mouse|bacteria|virus|tumou?r|neuron|expression|metabol|immune|mutation|therapy|cancer|biolog|ecolog",
    "ai_cs": r"neural network|deep learning|machine learning|transformer|language model|reinforcement learning|classification|convolutional|algorithm|dataset|training data|embedding|attention mechanism|computer vision|natural language|gradient descent|diffusion model|generative|benchmark|software|computational complexity",
}
_RX = {k: re.compile(v, re.I) for k, v in LEXICON.items()}
LABELS = ["physics", "chemistry", "biology", "ai_cs", "interdisciplinary", "other"]
MIN_HITS = 3


def weak_domain_scores(text: str) -> dict[str, int]:
    t = text[:6000]
    return {k: len(rx.findall(t)) for k, rx in _RX.items()}


def weak_labels(text: str) -> list[str]:
    """Multi-label output. 'interdisciplinary' when >=2 domains clear the threshold."""
    sc = weak_domain_scores(text)
    hit = [k for k, v in sc.items() if v >= MIN_HITS]
    if not hit:
        return ["other"]
    if len(hit) >= 2:
        hit.append("interdisciplinary")
    return hit


def primary_domain(text: str) -> str:
    sc = weak_domain_scores(text)
    k, v = max(sc.items(), key=lambda kv: kv[1])
    if v < MIN_HITS:
        return "other"
    hit = [d for d, n in sc.items() if n >= MIN_HITS]
    return "interdisciplinary" if len(hit) >= 2 and sorted(sc.values())[-2] >= 0.6 * v else k
