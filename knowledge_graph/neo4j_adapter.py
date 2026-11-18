"""Optional Neo4j export. UNTESTED against a live server (none installed here); Cypher generation is unit-tested."""
from __future__ import annotations
import json, re


def _q(v) -> str: return json.dumps(v if v is not None else "")


def to_cypher(g) -> list[str]:
    out = []
    for n, d in g.nodes(data=True):
        lab = (d.get("kind") or "node").capitalize()
        props = {k: v for k, v in d.items() if isinstance(v, (str, int, float)) and v is not None}
        out.append(f"MERGE (n:{lab} {{id: {_q(n)}}}) SET " + ", ".join(f"n.{k} = {_q(v)}" for k, v in props.items() if re.fullmatch(r"\w+", k)))
    for u, v, d in g.edges(data=True):
        rel = re.sub(r"\W", "_", d["rel"])
        props = {k: x for k, x in d.items() if isinstance(x, (str, int, float)) and k != "rel"}
        out.append(f"MATCH (a {{id: {_q(u)}}}), (b {{id: {_q(v)}}}) CREATE (a)-[r:{rel}]->(b) SET " + (", ".join(f"r.{k} = {_q(x)}" for k, x in props.items()) or "r.kind = 'unknown'"))
    return out


def push(g, uri: str, user: str, password: str, database: str = "neo4j"):
    from neo4j import GraphDatabase   # pip install neo4j
    with GraphDatabase.driver(uri, auth=(user, password)) as drv, drv.session(database=database) as s:
        for stmt in to_cypher(g): s.run(stmt)
