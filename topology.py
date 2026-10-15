"""
topology.py: Pure-Python Dependency Graph Engine for Autonomous Network Guardian.
Implements Directed Acyclic Graph (DAG) traversal, ancestor resolution,
and blast radius calculation with zero mandatory external dependencies.
Optionally integrates with NetworkX if installed.
"""

import json
from collections import deque
from typing import Dict, List, Set, Any, Optional

class DependencyGraph:
    """
    Directed Acyclic Graph representing network dependencies.
    An edge (U, V) implies that V depends on U (U is upstream, V is downstream).
    If U fails, V is inside U's blast radius.
    """
    def __init__(self, config_path: Optional[str] = None):
        self.node_metadata: Dict[str, Dict[str, Any]] = {}
        # Adjacency maps
        self.children: Dict[str, List[str]] = {}   # u -> list of downstream dependents
        self.parents: Dict[str, List[str]] = {}    # v -> list of upstream prerequisites
        
        if config_path:
            self.load_from_json(config_path)

    def load_from_json(self, filepath: str) -> None:
        """Load network topology and dependency relationships from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.node_metadata.clear()
        self.children.clear()
        self.parents.clear()

        # Register nodes
        for node in data.get("nodes", []):
            node_id = node["id"]
            self.node_metadata[node_id] = node
            self.children[node_id] = []
            self.parents[node_id] = []

        # Register directed dependencies (depends_on -> dependent)
        for dep in data.get("dependencies", []):
            u = dep["depends_on"]
            v = dep["dependent"]

            if u not in self.children:
                self.children[u] = []
            if v not in self.parents:
                self.parents[v] = []

            self.children[u].append(v)
            self.parents[v].append(u)

    def get_direct_prerequisites(self, node_id: str) -> List[str]:
        """Return immediate upstream parent nodes (nodes required by node_id)."""
        return self.parents.get(node_id, [])

    def get_direct_dependents(self, node_id: str) -> List[str]:
        """Return immediate downstream children nodes (nodes relying on node_id)."""
        return self.children.get(node_id, [])

    def get_upstream_ancestors(self, node_id: str) -> Set[str]:
        """
        Traverse parent links using Breadth-First Search (BFS) to find all
        upstream infrastructure components that node_id relies on.
        Time Complexity: O(V + E)
        """
        ancestors: Set[str] = set()
        queue = deque(self.parents.get(node_id, []))

        while queue:
            curr = queue.popleft()
            if curr not in ancestors:
                ancestors.add(curr)
                for parent in self.parents.get(curr, []):
                    if parent not in ancestors:
                        queue.append(parent)

        return ancestors

    def get_downstream_blast_radius(self, node_id: str) -> Set[str]:
        """
        Traverse child links using Breadth-First Search (BFS) to identify all
        downstream entities affected if node_id experiences failure.
        Time Complexity: O(V + E)
        """
        blast_radius: Set[str] = set()
        queue = deque(self.children.get(node_id, []))

        while queue:
            curr = queue.popleft()
            if curr not in blast_radius:
                blast_radius.add(curr)
                for child in self.children.get(curr, []):
                    if child not in blast_radius:
                        queue.append(child)

        return blast_radius

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """Return all registered nodes with metadata."""
        return list(self.node_metadata.values())

    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a specific node ID."""
        return self.node_metadata.get(node_id)

    def add_node(self, node_id: str, name: str, node_type: str, ip: str = "N/A") -> None:
        """Dynamically register a new network asset into the topology."""
        node_meta = {"id": node_id, "name": name, "type": node_type, "ip": ip}
        self.node_metadata[node_id] = node_meta
        if node_id not in self.children:
            self.children[node_id] = []
        if node_id not in self.parents:
            self.parents[node_id] = []

    def add_dependency(self, depends_on: str, dependent: str, description: str = "") -> None:
        """Dynamically link a dependent node to an upstream prerequisite."""
        if depends_on not in self.children:
            self.children[depends_on] = []
        if dependent not in self.parents:
            self.parents[dependent] = []

        if dependent not in self.children[depends_on]:
            self.children[depends_on].append(dependent)
        if depends_on not in self.parents[dependent]:
            self.parents[dependent].append(depends_on)
