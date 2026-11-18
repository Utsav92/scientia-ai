import networkx as nx
from knowledge_graph.graph_builder import build_graph, add_citations, pid, eid
from knowledge_graph import graph_queries as q
from knowledge_graph.neo4j_adapter import to_cypher
from extraction.findings import extract_paper
from common import connect

DOCS = {
 "1": "Paper One\n\nWe evaluated a Transformer on the QM9 dataset. Results show that accuracy improved by 5% over baselines. However, the approach cannot handle charged species.",
 "2": "Paper Two\n\nWe trained a Transformer and a CNN on the ImageNet dataset. Results show that accuracy improved significantly on ImageNet benchmarks.",
 "3": "Paper Three\n\nWe applied a CNN to the QM9 dataset for molecular property prediction. The CNN achieved accuracy of 90% in our experiments on molecules.",
 "4": "Paper Four\n\nWe studied perovskite thin films with density functional theory and measured band gaps for several samples in the lab.",
}


def make(tmp_path):
    db = tmp_path / "g.db"; con = connect(db)
    for i, t in DOCS.items():
        con.execute("INSERT INTO documents(id,owner,text,title,domain,year) VALUES(?,?,?,?,?,?)", (i, "", t, t.split("\n")[0], "ai_cs", 2020))
    con.commit()
    for i in DOCS: extract_paper(i, db_path=db)
    return build_graph(db_path=db, with_similarity=False)


def test_edges_carry_evidence_and_no_fake_citations(tmp_path):
    g = make(tmp_path)
    assert g.graph["stats"]["citation_edges"] == 0
    for u, v, d in g.edges(data=True):
        if d["kind"] == "extracted": assert d.get("quote"), (u, v, d)
    assert g.has_edge(pid("1"), eid("DATASET", "qm9"))
    assert any(d["rel"] == "EVALUATED_ON" for _, _, d in g.edges(data=True))


def test_related_and_common_methods(tmp_path):
    g = make(tmp_path)
    r = q.related_papers(g, "1")
    assert r["shared_entity"][0]["paper_id"] in ("2", "3")
    assert "qm9" in r["shared_entity"][0]["shared_entities"] or "transformer" in r["shared_entity"][0]["shared_entities"]
    assert r["citations"] == []                       # nothing invented
    assert q.common_methods(g, ["2", "3"]) == ["convolutional neural network"]
    assert q.search_entities(g, "qm9")[0]["n_papers"] == 2
    assert {t["label"] for t in q.connected_topics(g, eid("DATASET", "qm9"))} >= {"accuracy"}


def test_citations_only_for_known_papers(tmp_path):
    g = make(tmp_path)
    assert add_citations(g, [("1", "2"), ("1", "999")], "test-metadata") == 1
    assert q.related_papers(g, "1")["citations"][0]["paper_id"] == "2"


def test_subgraph_bounded_and_typed(tmp_path):
    g = make(tmp_path)
    s = q.subgraph(g, "concept", center="1", max_nodes=5)
    assert len(s["nodes"]) <= 5
    ev = q.subgraph(g, "evidence", center="1")
    assert any(n["kind"] in ("finding", "limitation") for n in ev["nodes"]) and all(e["quote"] for e in ev["edges"])
    assert all(e["kind"] in ("extracted", "semantic", "citation") for e in q.subgraph(g, "paper", center="1")["edges"])


def test_clusters_and_cypher(tmp_path):
    g = make(tmp_path)
    assert isinstance(q.clusters(g), list)
    cy = to_cypher(g)
    assert any("EVALUATED_ON" in c for c in cy) and all(c.startswith(("MERGE", "MATCH")) for c in cy)
