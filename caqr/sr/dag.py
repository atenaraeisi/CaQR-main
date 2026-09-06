from dataclasses import dataclass


class UnsupportedCircuitError(ValueError):
    pass


@dataclass(frozen=True)
class MeasurementSpec:
    logical_qubit: int
    classical_bit: int
    original_index: int


@dataclass(frozen=True)
class OperationNode:
    node_id: int
    original_index: int
    instruction: object
    logical_qubits: tuple

    @property
    def name(self):
        return self.instruction.name


class RegularDAG:
    def __init__(self, nodes):
        self.nodes = list(nodes)
        self.nodes_by_id = {node.node_id: node for node in nodes}
        self.successors = {node.node_id: set() for node in nodes}
        self.predecessors = {node.node_id: set() for node in nodes}
        self.remaining_ids = set(self.nodes_by_id)
        self.remaining_predecessor_count = {node.node_id: 0 for node in nodes}
        self._build_edges()

    def _build_edges(self):
        last_for_qubit = {}
        for node in self.nodes:
            for logical in node.logical_qubits:
                previous = last_for_qubit.get(logical)
                if previous is not None:
                    self.successors[previous].add(node.node_id)
                    self.predecessors[node.node_id].add(previous)
                last_for_qubit[logical] = node.node_id
        self.remaining_predecessor_count = {
            node.node_id: len(self.predecessors[node.node_id]) for node in self.nodes
        }

    def has_remaining(self):
        return bool(self.remaining_ids)

    def remaining_count(self):
        return len(self.remaining_ids)

    def frontier(self):
        return [
            self.nodes_by_id[node_id]
            for node_id in sorted(self.remaining_ids)
            if self.remaining_predecessor_count[node_id] == 0
        ]

    def remove(self, node_id):
        if node_id not in self.remaining_ids:
            raise ValueError(f"DAG node {node_id} has already been removed")
        self.remaining_ids.remove(node_id)
        for successor in self.successors[node_id]:
            if successor in self.remaining_ids:
                self.remaining_predecessor_count[successor] -= 1

    def remaining_operations_per_logical(self):
        counts = {}
        for node_id in self.remaining_ids:
            for logical in self.nodes_by_id[node_id].logical_qubits:
                counts[logical] = counts.get(logical, 0) + 1
        return counts

    def future_two_qubit_interactions(self, logical_qubit):
        interactions = []
        for node_id in sorted(self.remaining_ids):
            node = self.nodes_by_id[node_id]
            if len(node.logical_qubits) == 2 and logical_qubit in node.logical_qubits:
                left, right = node.logical_qubits
                other = right if left == logical_qubit else left
                interactions.append((node, other))
        return interactions

    def unscheduled_node_ids(self):
        return sorted(self.remaining_ids)


def preprocess_regular_circuit(circuit):
    nodes = []
    measurement_by_logical = {}
    measurement_order = []
    used_classical_bits = set()
    seen_measurement = False

    for index, (instruction, qargs, cargs) in enumerate(circuit.data):
        if getattr(instruction, "condition", None) is not None:
            raise UnsupportedCircuitError(
                f"Unsupported classical condition on instruction {index}: {instruction.name}"
            )
        if getattr(instruction, "blocks", None):
            raise UnsupportedCircuitError(
                f"Unsupported control-flow instruction {index}: {instruction.name}"
            )

        qbits = tuple(circuit.find_bit(q).index for q in qargs)
        cbits = tuple(circuit.find_bit(c).index for c in cargs)

        if instruction.name == "measure":
            if len(qbits) != 1 or len(cbits) != 1:
                raise UnsupportedCircuitError(
                    f"Unsupported measurement shape at instruction {index}"
                )
            logical = qbits[0]
            classical = cbits[0]
            if logical in measurement_by_logical:
                raise UnsupportedCircuitError(
                    f"Logical qubit {logical} has multiple measurements; "
                    "Phase 1 supports at most one final measurement per logical qubit"
                )
            if classical in used_classical_bits:
                raise UnsupportedCircuitError(
                    f"Classical bit {classical} is written by multiple measurements"
                )
            seen_measurement = True
            spec = MeasurementSpec(logical, classical, index)
            measurement_by_logical[logical] = spec
            measurement_order.append(spec)
            used_classical_bits.add(classical)
            continue

        if seen_measurement:
            raise UnsupportedCircuitError(
                "Phase 1 supports final measurements only; found a quantum "
                f"instruction after measurement at instruction {index}"
            )
        if instruction.name == "reset":
            raise UnsupportedCircuitError(
                f"Unsupported pre-existing reset at instruction {index}"
            )
        if cargs:
            raise UnsupportedCircuitError(
                f"Unsupported classical operands on instruction {index}: {instruction.name}"
            )
        if len(qbits) == 0 or len(qbits) > 2:
            raise UnsupportedCircuitError(
                f"Unsupported instruction width at instruction {index}: "
                f"{instruction.name} uses {len(qbits)} qubits"
            )

        nodes.append(
            OperationNode(
                node_id=len(nodes),
                original_index=index,
                instruction=instruction,
                logical_qubits=qbits,
            )
        )

    return RegularDAG(nodes), measurement_by_logical, measurement_order
