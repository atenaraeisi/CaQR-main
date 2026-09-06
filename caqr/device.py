import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DeviceInfo:
    name: str
    num_qubits: int
    coupling_edges: list
    readout_errors: dict = None
    cx_errors: dict = None
    operation_durations: dict = None

    @classmethod
    def from_json(cls, path):
        data = json.loads(Path(path).read_text())
        required = ["num_qubits", "coupling_edges"]
        for key in required:
            if key not in data:
                raise ValueError(f"Device file {path} is missing required field {key!r}")
        return cls(
            name=data.get("name", Path(path).stem),
            num_qubits=int(data["num_qubits"]),
            coupling_edges=[tuple(edge) for edge in data["coupling_edges"]],
            readout_errors=data.get("readout_errors"),
            cx_errors=data.get("cx_errors"),
            operation_durations=data.get("operation_durations"),
        )

    def directed_edges(self):
        return [tuple(edge) for edge in self.coupling_edges]

    def undirected_neighbors(self):
        neighbors = {i: set() for i in range(self.num_qubits)}
        for src, dst in self.coupling_edges:
            self._validate_physical(src)
            self._validate_physical(dst)
            neighbors[src].add(dst)
            neighbors[dst].add(src)
        return neighbors

    def is_adjacent(self, left, right):
        # REPRODUCTION DESIGN CHOICE: Phase 1 uses an undirected view of the
        # coupling graph for compliance and routing. Directed edges are kept in
        # DeviceInfo for later gate-direction and error-aware modeling.
        return right in self.undirected_neighbors()[left]

    def degree(self, physical):
        return len(self.undirected_neighbors()[physical])

    def shortest_path(self, start, goal):
        if start == goal:
            return [start]
        neighbors = self.undirected_neighbors()
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            node, path = queue.popleft()
            for nxt in sorted(neighbors[node]):
                if nxt in visited:
                    continue
                if nxt == goal:
                    return path + [nxt]
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
        raise ValueError(f"No coupling path between physical qubits {start} and {goal}")

    def distance(self, start, goal):
        return len(self.shortest_path(start, goal)) - 1

    def _validate_physical(self, physical):
        if physical < 0 or physical >= self.num_qubits:
            raise ValueError(
                f"Physical qubit {physical} is outside device size {self.num_qubits}"
            )
