from rag.citations import split_claims, build_citation_table
from rag.verification import verify_answer, revise_answer, lexical_overlap, numbers_grounded
from retrieval.hybrid import Evidence

PASS = "Diffusion models improved sample validity by 12.5% on molecular generation benchmarks compared to autoregressive baselines."
CIT = {1: {"passage": PASS, "title": "T", "section": "abstract"}}


def test_split_claims():
    c = split_claims("A is true [1]. Interpretation: maybe B. C is true [1][2].")
    assert c[0]["markers"] == [1] and c[1]["is_interpretation"] and c[2]["markers"] == [1, 2]


def test_supported_unsupported_and_numbers():
    ans = ("Diffusion models improved sample validity on molecular generation benchmarks [1]. "
           "Diffusion models improved validity by 40% on molecular benchmarks [1]. "      # wrong number
           "Transformers always win [1]. "                                                  # not in passage
           "Protein folding is solved.")                                                    # uncited
    r = verify_answer(ans, CIT, nli=None)
    st = [c["status"] for c in r["claims"]]
    assert st == ["supported", "unsupported", "unsupported", "uncited"]
    kept = revise_answer(ans, r)
    assert "40%" not in kept and "Protein folding" not in kept and "validity on molecular" in kept


def test_invalid_marker():
    r = verify_answer("Something [9].", CIT)
    assert r["claims"][0]["status"] == "invalid_citation"


def test_doi_never_invented():
    e = Evidence("1", "1:0", "Title", "abstract", 1.0, "text", 0, 4, {"source": "s2ag/train"})
    t = build_citation_table([e])
    assert t[1]["doi"] is None


def test_understand_compare_cores():
    from rag.pipeline import understand
    u = understand("Compare the latest evidence for diffusion models versus autoregressive Transformers in scientific data generation.")
    assert u["mode"] == "compare" and len(u["sides"]) == 2
    assert "diffusion" in u["cores"][0] and any(w.startswith("autoregress") for w in u["cores"][1])
    assert u["temporal_claim_note"]


def test_trailing_marker_stays_with_its_sentence():
    c = split_claims("Neural networks predict stability. [2] Second claim here [1][3]. Third. [4]")
    assert [x["markers"] for x in c] == [[2], [1, 3], [4]]
    assert not any(x["text"].startswith("[") for x in c)


def test_windowed_nli_support_paraphrase_and_contradiction():
    """Needs the NLI model (downloads once). Checks: paraphrase supported, contradiction/unrelated flagged."""
    import pytest
    try:
        from models.nli import get_nli
        nli = get_nli(); nli.probs(["a"], ["b"])
    except Exception as e:  # offline CI
        pytest.skip(f"NLI model unavailable: {e}")
    passage = ("Molecular generation was benchmarked on three datasets. Diffusion models improved sample validity by 12.5% "
               "compared with autoregressive baselines. Training required 4 GPUs. Results varied across datasets and the gains were smaller on the largest set.")
    cit = {1: {"passage": passage}}
    ans = ("Diffusion models gave better sample validity than autoregressive baselines [1]. "
           "Autoregressive baselines achieved higher validity than diffusion models [1]. "
           "The mitochondria is the powerhouse of the cell [1].")
    r = verify_answer(ans, cit, nli)
    assert [c["status"] for c in r["claims"]] == ["supported", "unsupported", "unsupported"]


def test_leading_markers_and_no_cross_paragraph_leak():
    ans = "[2][4] Neural nets predict stability. Second sentence [1].\n\n[2] The testbed is open access."
    c = split_claims(ans)
    assert [x["markers"] for x in c] == [[2, 4], [1], [2]]
    assert c[2]["text"].startswith("The testbed")


def test_comma_style_markers():
    c = split_claims("Nets predict stability [1, 2]. Other claim [3,4].")
    assert [x["markers"] for x in c] == [[1, 2], [3, 4]]
