"""Rule/gazetteer scientific entity extraction + normalisation.

This is a transparent BASELINE (no trained NER model exists in this repo yet). It favours precision on a fixed vocabulary
and will miss novel entities; recall is unmeasured because no gold annotations are available. Every entity is a literal
span of the source text with offsets.
"""
from __future__ import annotations
import re
from .schemas import Entity

ALIASES = {  # surface (lowercase, de-pluralised) -> canonical
    "cnn": "convolutional neural network", "convnet": "convolutional neural network", "convolutional neural network": "convolutional neural network",
    "rnn": "recurrent neural network", "lstm": "lstm", "gru": "gru", "gnn": "graph neural network", "gcn": "graph convolutional network",
    "transformer": "transformer", "bert": "bert", "gpt": "gpt", "vae": "variational autoencoder", "gan": "generative adversarial network",
    "svm": "support vector machine", "support vector machine": "support vector machine", "random forest": "random forest",
    "dft": "density functional theory", "density functional theory": "density functional theory", "md": "molecular dynamics", "molecular dynamics": "molecular dynamics",
    "pcr": "pcr", "qpcr": "pcr", "crispr": "crispr", "nmr": "nmr", "xrd": "x-ray diffraction", "x-ray diffraction": "x-ray diffraction",
    "monte carlo": "monte carlo", "finite element": "finite element method", "finite element method": "finite element method",
    "reinforcement learning": "reinforcement learning", "deep learning": "deep learning", "machine learning": "machine learning",
    "diffusion model": "diffusion model", "neural network": "neural network", "attention mechanism": "attention mechanism",
    "logistic regression": "logistic regression", "linear regression": "linear regression", "k-means": "k-means", "pca": "principal component analysis",
    "principal component analysis": "principal component analysis", "bayesian": "bayesian inference", "bayesian inference": "bayesian inference",
}
METHOD_TERMS = sorted(ALIASES, key=len, reverse=True)
METRICS = r"accuracy|precision|recall|f1(?:[- ]score)?|auc|roc[- ]auc|rmse|mae|mse|bleu|perplexity|sensitivity|specificity|r\^?2|correlation coefficient|yield|selectivity|turnover frequency"
BIO = r"protein(?:s)?|gene(?:s)?|mutation(?:s)?|enzyme(?:s)?|receptor(?:s)?|antibod(?:y|ies)|mrna|rna|dna|peptide(?:s)?|genome(?:s)?|neuron(?:s)?|cell line(?:s)?"
MATERIAL = r"perovskite(?:s)?|graphene|nanoparticle(?:s)?|nanotube(?:s)?|polymer(?:s)?|alloy(?:s)?|ceramic(?:s)?|semiconductor(?:s)?|superconductor(?:s)?|zeolite(?:s)?|silicon|thin film(?:s)?"
UNITS = r"nm|μm|um|mm|cm|km|m/s|hz|khz|mhz|ghz|thz|ev|mev|gev|tev|kev|k|°c|mol|mmol|mg|kg|g|ml|μl|mpa|gpa|pa|v|mv|ma|a|w|mw|kw|j|kj|s|ms|ns|ps|fs|%|db|t|gauss"
QUANT = re.compile(rf"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?:\s?[×x]\s?10\^?[-−]?\d+)?\s?(?:{UNITS})(?![\w])", re.I)
CHEM = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}(?:\d*[+-])?\b")
ELEMENTS = set("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Sr Y Zr Nb Mo Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pt Au Hg Pb Bi U".split())
DATASET = re.compile(r"\b((?:[A-Z][\w\-]*[ ]?){1,3}(?:dataset|data set|benchmark|corpus|database))\b")
NAMED_DS = re.compile(r"\b(ImageNet|CIFAR-?\d+|MNIST|QM9|ZINC|PubChem|ChEMBL|UniProt|PDB|CASP\d*|AlphaFold DB|GLUE|SQuAD|MS MARCO|BEIR|SciFact|TCGA|GEO|Materials Project|OQMD|COCO|WikiText)\b")


def _stem(s: str) -> str:
    s = s.lower().strip()
    return re.sub(r"(?<=[a-z])s$", "", s) if not s.endswith(("ss", "is", "us")) else s


def canonicalize(text: str, etype: str) -> str:
    t = re.sub(r"\s+", " ", text.lower().strip(" .,;:()"))
    if t in ALIASES: return ALIASES[t]
    st = _stem(t)
    if st in ALIASES: return ALIASES[st]
    if etype in ("DATASET", "CHEMICAL"): return t.replace(" data set", " dataset") if etype == "DATASET" else text.strip()
    return st


def _valid_formula(s: str) -> bool:
    """Chemical formula heuristic. Rejects all-caps acronyms that merely spell element symbols (SPSS, PPS, UICC),
    grant/ID codes with long digit runs (SC0019409) and single-element strings."""
    parts = re.findall(r"[A-Z][a-z]?", s)
    if len(parts) < 2 or len(set(parts)) < 2 or not all(p in ELEMENTS for p in parts):
        return False
    if re.search(r"\d{4,}", s) or s.endswith("-") and not re.search(r"\d", s):
        return False
    has_digit = any(c.isdigit() for c in s)
    has_two_letter_symbol = any(len(p) == 2 for p in parts)       # e.g. NaCl, FeO
    return has_digit or has_two_letter_symbol


def extract_entities(text: str) -> list[Entity]:
    out: list[Entity] = []
    seen: set[tuple[int, int]] = set()

    def add(m: re.Match, etype: str, g=0):
        a, b = m.start(g), m.end(g)
        if any(not (b <= s or a >= e) for s, e in seen): return
        seen.add((a, b)); surf = text[a:b]
        out.append(Entity(text=surf, type=etype, canonical=canonicalize(surf, etype), char_start=a, char_end=b))

    for rx, t in ((NAMED_DS, "DATASET"), (DATASET, "DATASET")):
        for m in rx.finditer(text): add(m, t)
    for term in METHOD_TERMS:
        for m in re.finditer(rf"(?<![\w-]){re.escape(term)}(?:s|es)?(?![\w-])", text, re.I):
            core = text[m.start():m.start() + len(term)]
            if len(term) <= 4 and not core.isupper() and term not in ("bert", "gpt", "lstm", "gru"):
                continue   # short acronyms must be written in capitals ("MD", "GAN"), not ordinary words
            t = "MODEL" if term in ("transformer", "bert", "gpt", "lstm", "gru", "cnn", "rnn", "gnn", "gcn", "vae", "gan", "convnet", "diffusion model", "neural network", "convolutional neural network") else "METHOD"
            add(m, t)
    for m in re.finditer(rf"(?<![\w-])(?:{METRICS})(?![\w-])", text, re.I): add(m, "METRIC")
    for m in re.finditer(rf"(?<![\w-])(?:{BIO})(?![\w-])", text, re.I): add(m, "BIOLOGICAL_ENTITY")
    for m in re.finditer(rf"(?<![\w-])(?:{MATERIAL})(?![\w-])", text, re.I): add(m, "MATERIAL")
    for m in CHEM.finditer(text):
        if _valid_formula(m.group(0)): add(m, "CHEMICAL")
    for m in QUANT.finditer(text): add(m, "PHYSICAL_QUANTITY")
    return sorted(out, key=lambda e: e.char_start or 0)


def dedupe(entities: list[Entity]) -> list[Entity]:
    best: dict[tuple[str, str], Entity] = {}
    for e in entities:
        best.setdefault((e.type, e.canonical), e)
    return list(best.values())
