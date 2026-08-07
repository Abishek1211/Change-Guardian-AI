"""The dependency graph agent 3 traverses.

Nodes are services, databases, APIs, Kafka events, and shared libraries. Edges
carry a `rel` label so the frontend can style them differently - a CALLS edge
and a USES_DB edge mean very different things to an on-call engineer.
"""

from __future__ import annotations

import networkx as nx

from ..data import api_consumers, database_users, event_consumers, libraries, services


def build_graph() -> nx.DiGraph:
    graph = nx.DiGraph()

    for name, info in services.items():
        graph.add_node(name, node_type="service", criticality=info["criticality"], team=info["team"])

    for db, info in database_users.items():
        graph.add_node(db, node_type="database")
        for svc in info["shared_by"]:
            graph.add_edge(svc, db, rel="USES_DB")

    for api, info in api_consumers.items():
        graph.add_node(api, node_type="api")
        graph.add_edge(info["provider"], api, rel="PROVIDES_API")
        for consumer in info["consumers"]:
            graph.add_edge(consumer, api, rel="CONSUMES_API")
            graph.add_edge(consumer, info["provider"], rel="CALLS")

    for event, info in event_consumers.items():
        graph.add_node(event, node_type="kafka_event")
        graph.add_edge(info["producer"], event, rel="PRODUCES_EVENT")
        for consumer in info["consumers"]:
            graph.add_edge(consumer, event, rel="CONSUMES_EVENT")

    for lib, info in libraries.items():
        graph.add_node(lib, node_type="library")
        for svc in info["used_by"]:
            graph.add_edge(svc, lib, rel="DEPENDS_ON")

    return graph


G: nx.DiGraph = build_graph()


def get_affected_services(service_name: str, graph: nx.DiGraph | None = None) -> list[str]:
    """Services reachable from `service_name` in either direction.

    Both directions matter: descendants are what this service depends on and
    could break by changing, ancestors are what depends on it and will feel the
    change. The blast radius is the union.
    """
    graph = graph if graph is not None else G
    if service_name not in graph:
        return []

    affected = {
        node
        for node in (*nx.descendants(graph, service_name), *nx.ancestors(graph, service_name))
        if graph.nodes[node].get("node_type") == "service"
    }
    affected.discard(service_name)
    return sorted(affected)


def graph_payload(graph: nx.DiGraph | None = None) -> dict:
    """Serialise to `{nodes, edges}` for React Flow."""
    graph = graph if graph is not None else G
    return {
        "nodes": [
            {
                "id": name,
                "type": attrs.get("node_type", "unknown"),
                "criticality": attrs.get("criticality"),
                "team": attrs.get("team"),
            }
            for name, attrs in graph.nodes(data=True)
        ],
        "edges": [
            {"source": src, "target": dst, "rel": attrs.get("rel", "")}
            for src, dst, attrs in graph.edges(data=True)
        ],
    }
