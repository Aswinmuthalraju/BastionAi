import json
import re
from typing import Any, Dict, List

import kuzu

from app import config

_EQUIPMENT_CODE_PATTERN = re.compile(r"\b([PLVT])-?(\d{3})\b", re.IGNORECASE)
_DOC_CODE_PATTERN = re.compile(r"\b(INSP|SOP)-(\d{3,4})\b", re.IGNORECASE)


def extract_equipment_ids(text: str) -> List[str]:
    """Finds equipment/document references in real text, accepting both 'P101' and 'P-101' forms."""
    ids = set()
    for m in _EQUIPMENT_CODE_PATTERN.finditer(text):
        ids.add(f"{m.group(1).upper()}{m.group(2)}")
    for m in _DOC_CODE_PATTERN.finditer(text):
        ids.add(f"{m.group(1).upper()}-{m.group(2)}")
    return sorted(ids)


class GraphStore:
    """
    Real embedded property graph (Kùzu) with a genuine Cypher query engine —
    replacing the previous in-memory dict that only pretended to be Neo4j.
    The `cypher_executed` string returned to callers is the literal query run,
    not a decorative label.
    """

    def __init__(self):
        self.db = kuzu.Database(config.KUZU_PATH)
        self.conn = kuzu.Connection(self.db)
        self._ensure_schema()
        self._seed_baseline_equipment_if_empty()

    def _ensure_schema(self):
        try:
            self.conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Equipment("
                "id STRING, label STRING, name STRING, extra STRING, PRIMARY KEY(id))"
            )
            self.conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Document(doc_id STRING, title STRING, PRIMARY KEY(doc_id))"
            )
            self.conn.execute(
                "CREATE REL TABLE IF NOT EXISTS RELATED(FROM Equipment TO Equipment, relation STRING)"
            )
            self.conn.execute(
                "CREATE REL TABLE IF NOT EXISTS MENTIONS(FROM Document TO Equipment)"
            )
        except RuntimeError:
            pass  # tables already exist from a prior run

    def _node_exists(self, node_id: str) -> bool:
        res = self.conn.execute(
            "MATCH (e:Equipment {id: $id}) RETURN e.id", {"id": node_id}
        )
        return res.has_next()

    def _seed_baseline_equipment_if_empty(self):
        if self._node_exists("P101"):
            return

        nodes = [
            ("P101", "Equipment", "High-Pressure Feed Pump P-101", {"type": "Centrifugal Pump", "criticality": "HIGH"}),
            ("L204", "Pipeline", "Crude Oil Line L-204", {"rating": "Class 300", "diameter": "6-inch"}),
            ("V204", "Valve", "Hydrocarbon Isolation Valve V-204", {"type": "Gate Valve", "status": "Normally Open"}),
            ("T101", "Storage", "Crude Storage Tank T-101", {"capacity": "50000 bbl"}),
            ("INSP-2026", "InspectionReport", "Annual Inspection Report 2026", {"report_id": "INSP-2026-9", "min_thickness": "4.2mm", "status": "PASSED"}),
            ("SOP-771", "SOP", "Pump Vibration Bypass Procedure", {"doc_id": "SOP-771"}),
        ]
        for node_id, label, name, extra in nodes:
            self.add_equipment(node_id, label, name, extra)

        edges = [
            ("T101", "L204", "FEEDS_INTO"),
            ("L204", "P101", "SUCTION_LINE"),
            ("P101", "V204", "DISCHARGE_ISOLATION"),
            ("P101", "INSP-2026", "HAS_INSPECTION"),
            ("P101", "SOP-771", "GOVERNED_BY"),
            ("V204", "INSP-2026", "INSPECTED_IN"),
        ]
        for src, dst, relation in edges:
            self.add_relation(src, dst, relation)

    def add_equipment(self, node_id: str, label: str, name: str, extra: Dict[str, Any]):
        self.conn.execute(
            "MERGE (e:Equipment {id: $id}) SET e.label = $label, e.name = $name, e.extra = $extra",
            {"id": node_id, "label": label, "name": name, "extra": json.dumps(extra)},
        )

    def add_relation(self, src_id: str, dst_id: str, relation: str):
        self.conn.execute(
            "MATCH (a:Equipment {id: $src}), (b:Equipment {id: $dst}) "
            "CREATE (a)-[:RELATED {relation: $relation}]->(b)",
            {"src": src_id, "dst": dst_id, "relation": relation},
        )

    def link_document_mentions(self, doc_id: str, title: str, text: str) -> List[str]:
        """Scans real ingested document text for equipment references and links them in the graph."""
        mentioned = extract_equipment_ids(text)
        known = [m for m in mentioned if self._node_exists(m)]
        if not known:
            return []
        self.conn.execute("MERGE (d:Document {doc_id: $id}) SET d.title = $title", {"id": doc_id, "title": title})
        for equip_id in known:
            self.conn.execute(
                "MATCH (d:Document {doc_id: $doc_id}), (e:Equipment {id: $equip_id}) "
                "CREATE (d)-[:MENTIONS]->(e)",
                {"doc_id": doc_id, "equip_id": equip_id},
            )
        return known

    def _row_to_node(self, node_id: str, label: str, name: str, extra_json: str) -> Dict[str, Any]:
        extra = json.loads(extra_json) if extra_json else {}
        return {"id": node_id, "label": label, "name": name, **extra}

    def query_equipment_lineage(self, start_equipment_id: str = "P101") -> Dict[str, Any]:
        if not self._node_exists(start_equipment_id):
            start_equipment_id = "P101"

        cypher = (
            "MATCH (a:Equipment)-[r:RELATED]-(b:Equipment) "
            "WHERE a.id = $start "
            "RETURN a.id, a.label, a.name, a.extra, r.relation, b.id, b.label, b.name, b.extra"
        )
        result = self.conn.execute(cypher, {"start": start_equipment_id})

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, str]] = []
        seen_edge_keys = set()
        first_hop_ids = set()

        def add_edge(a_id: str, b_id: str, relation: str):
            key = tuple(sorted((a_id, b_id))) + (relation,)
            if key in seen_edge_keys:
                return
            seen_edge_keys.add(key)
            edges.append({"source": a_id, "target": b_id, "relation": relation})

        while result.has_next():
            a_id, a_label, a_name, a_extra, relation, b_id, b_label, b_name, b_extra = result.get_next()
            nodes[a_id] = self._row_to_node(a_id, a_label, a_name, a_extra)
            nodes[b_id] = self._row_to_node(b_id, b_label, b_name, b_extra)
            add_edge(a_id, b_id, relation)
            first_hop_ids.add(b_id)

        # Second hop, run as its own real query per discovered neighbor.
        for neighbor_id in list(first_hop_ids):
            hop2 = self.conn.execute(cypher, {"start": neighbor_id})
            while hop2.has_next():
                a_id, a_label, a_name, a_extra, relation, b_id, b_label, b_name, b_extra = hop2.get_next()
                nodes[a_id] = self._row_to_node(a_id, a_label, a_name, a_extra)
                nodes[b_id] = self._row_to_node(b_id, b_label, b_name, b_extra)
                add_edge(a_id, b_id, relation)

        return {
            "query_equipment": start_equipment_id,
            "cypher_executed": cypher.replace("$start", f"'{start_equipment_id}'"),
            "nodes": list(nodes.values()),
            "edges": edges,
        }


graph_store = GraphStore()
