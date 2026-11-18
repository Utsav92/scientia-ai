import json, gzip
from ingestion.metadata import normalize_text, classify_heading, split_paragraphs
from ingestion.chunking import chunk_document, STRATEGIES
from ingestion.deduplication import content_hash, NearDupIndex
from ingestion.pes2o_loader import ingest
from common import connect

TEXT = ("Deep Diffusion for Molecules\n\nABSTRACT\nWe study diffusion models for molecule generation. "
        "Results improve by 3.2% over baselines. Energy is 5×10^-3 eV.\n\nIntroduction\n" + "Sentence about method. " * 80 +
        "\n\nResults\nThe H2O + CO2 -> H2CO3 reaction was measured [12]. " * 5)


def test_normalize_preserves_science():
    t = normalize_text("E = 5×10^-3 eV;​ H₂O → CO₂ [12] x­ y")
    assert "5×10^-3" in t and "H₂O" in t and "[12]" in t and "​" not in t


def test_headings():
    assert classify_heading("2. Materials and Methods") == "methodology"
    assert classify_heading("This is a long sentence, not a heading at all of the paper.") is None


def test_offsets_are_exact_for_all_strategies():
    for s in STRATEGIES:
        for c in chunk_document("d1", TEXT, s, 60, 10):
            assert TEXT[c.char_start:c.char_end] == c.text
            assert c.n_tokens <= 60 + 5


def test_section_chunks_do_not_cross_sections():
    secs = {c.section for c in chunk_document("d1", TEXT, "section", 60, 10)}
    assert {"abstract", "introduction", "results"} <= secs


def test_dedup():
    assert content_hash("Hello, World!") == content_hash("hello world")
    nd = NearDupIndex()
    a = "the quick brown fox jumps over the lazy dog " * 20
    assert nd.check_and_add("a", a) is None
    assert nd.check_and_add("b", a + " extra") == "a"
    assert nd.check_and_add("c", "totally different text about quantum chromodynamics " * 20) is None


def test_ingest_resume_and_validation(tmp_path):
    f = tmp_path / "s.json.gz"
    recs = [{"id": str(i), "text": f"Paper {i} on protein folding with neural networks\n\n" + ("unique sentence number %d about topic %d. " % (i, i * 7)) * 30,
             "source": "s2ag/train", "created": "2020-01-01T00:00:00.000Z", "version": "v2", "added": "x"} for i in range(30)]
    recs.append({"id": "bad", "text": "x"})
    recs.append(dict(recs[0]))  # duplicate id
    with gzip.open(f, "wt") as fh:
        fh.write("\n".join(json.dumps(r) for r in recs))
    db = tmp_path / "t.db"
    r1 = ingest(10, db_path=db, local_file=str(f), resume=False, language=None)
    assert r1["stats"]["stored"] == 10
    r2 = ingest(25, db_path=db, local_file=str(f), resume=True, language=None)
    assert r2["stats"]["total_documents"] == 25
    con = connect(db)
    assert con.execute("SELECT COUNT(DISTINCT id) FROM documents").fetchone()[0] == 25
    r3 = ingest(100, db_path=db, local_file=str(f), resume=True, language=None)
    assert r3["stats"]["invalid"] == 1          # the too-short record
    assert r3["stats"]["total_documents"] == 30  # duplicate id was not re-added


def test_language_filter(tmp_path):
    f = tmp_path / "s.json"
    en = "Protein folding is studied with neural networks that predict structure from sequence data. " * 6
    de = "Die Proteinfaltung wird mit neuronalen Netzen untersucht, um die Struktur aus der Sequenz vorherzusagen. " * 6
    f.write_text(json.dumps({"id": "en1", "text": "Title of an English paper\n\n" + en}) + "\n" +
                 json.dumps({"id": "de1", "text": "Titel eines deutschen Artikels\n\n" + de}))
    r = ingest(5, db_path=tmp_path / "l.db", local_file=str(f), resume=False)
    assert r["stats"]["stored"] == 1 and r["stats"]["non_english"] == 1
