from dataclasses import dataclass, field
from qiskit import ClassicalRegister
from qiskit import QuantumCircuit
from qiskit import QuantumRegister


@dataclass
class SRState:
    input_circuit: object
    device: object
    output: QuantumCircuit
    logical_to_physical: dict = field(default_factory=dict)
    physical_to_logical: dict = field(default_factory=dict)
    physicalList: list = field(default_factory=list)
    physical_fresh: dict = field(default_factory=dict)
    reuse_ready_from: dict = field(default_factory=dict)
    completed_logicals: set = field(default_factory=set)
    remaining_operations: dict = field(default_factory=dict)
    emitted_measurements: set = field(default_factory=set)
    scheduled_original_node_ids: list = field(default_factory=list)
    inserted_swap_count: int = 0
    routed_two_qubit_operation_count: int = 0
    used_physical_qubits: set = field(default_factory=set)
    mapping_history: list = field(default_factory=list)
    reuse_events: list = field(default_factory=list)
    reclaim_events: list = field(default_factory=list)
    swap_events: list = field(default_factory=list)
    measurement_events: list = field(default_factory=list)

    @classmethod
    def create(cls, input_circuit, device, dag):
        qreg_name = input_circuit.qregs[0].name if input_circuit.qregs else "q"
        qreg = QuantumRegister(device.num_qubits, qreg_name)
        cregs = [
            ClassicalRegister(creg.size, creg.name)
            for creg in input_circuit.cregs
        ]
        output = QuantumCircuit(qreg, *cregs)
        state = cls(
            input_circuit=input_circuit,
            device=device,
            output=output,
            physical_to_logical={i: None for i in range(device.num_qubits)},
            physicalList=list(range(device.num_qubits)),
            physical_fresh={i: True for i in range(device.num_qubits)},
            reuse_ready_from={i: None for i in range(device.num_qubits)},
            remaining_operations=dag.remaining_operations_per_logical(),
        )
        state.assert_invariants()
        return state

    def assign_logical(self, logical, physical, reason, node_id=None):
        if logical in self.logical_to_physical:
            return self.logical_to_physical[logical]
        if physical not in self.physicalList:
            raise RuntimeError(
                f"Physical qubit {physical} is not available for logical q{logical}"
            )
        if not self.physical_fresh[physical]:
            raise RuntimeError(
                f"Physical qubit {physical} is listed free but is not fresh"
            )

        previous_owner = self.reuse_ready_from[physical]
        if previous_owner is not None and previous_owner != logical:
            event = {
                "physical": physical,
                "previous_logical": previous_owner,
                "new_logical": logical,
                "node_id": node_id,
            }
            self.reuse_events.append(event)

        self.physicalList.remove(physical)
        self.physical_to_logical[physical] = logical
        self.logical_to_physical[logical] = physical
        self.physical_fresh[physical] = False
        self.reuse_ready_from[physical] = None
        self.used_physical_qubits.add(physical)
        self.mapping_history.append(
            {
                "event": "map",
                "logical": logical,
                "physical": physical,
                "reason": reason,
                "node_id": node_id,
            }
        )
        self.assert_invariants()
        return physical

    def apply_swap(self, left, right, reason="routing", node_id=None):
        if left == right:
            return False
        if not self.device.is_adjacent(left, right):
            raise RuntimeError(f"Cannot SWAP non-adjacent physical qubits {left}, {right}")

        owner_left = self.physical_to_logical[left]
        owner_right = self.physical_to_logical[right]
        if owner_left is None and owner_right is None:
            return False
        free_marker_left = self.reuse_ready_from[left] if owner_left is None else None
        free_marker_right = self.reuse_ready_from[right] if owner_right is None else None

        self.output.swap(left, right)
        self.inserted_swap_count += 1

        self.physical_to_logical[left], self.physical_to_logical[right] = (
            owner_right,
            owner_left,
        )
        if owner_left is not None:
            self.logical_to_physical[owner_left] = right
        if owner_right is not None:
            self.logical_to_physical[owner_right] = left

        self.reuse_ready_from[left], self.reuse_ready_from[right] = (
            free_marker_right if owner_right is None else None,
            free_marker_left if owner_left is None else None,
        )
        self._refresh_free_state()
        event = {
            "left": left,
            "right": right,
            "owner_left_before": owner_left,
            "owner_right_before": owner_right,
            "reason": reason,
            "node_id": node_id,
        }
        self.swap_events.append(event)
        self.mapping_history.append({"event": "swap", **event})
        self.assert_invariants()
        return True

    def append_operation(self, node):
        physical_qubits = [self.logical_to_physical[q] for q in node.logical_qubits]
        if len(physical_qubits) == 2:
            left, right = physical_qubits
            if not self.device.is_adjacent(left, right):
                raise RuntimeError(
                    f"Two-qubit operation {node.name} on logical {node.logical_qubits} "
                    f"mapped to non-adjacent physical qubits {left}, {right}"
                )
            self.routed_two_qubit_operation_count += 1
        self.output.append(
            node.instruction,
            [self.output.qubits[p] for p in physical_qubits],
            [],
        )
        self.scheduled_original_node_ids.append(node.node_id)
        for logical in set(node.logical_qubits):
            self.remaining_operations[logical] = self.remaining_operations.get(logical, 0) - 1
            if self.remaining_operations[logical] < 0:
                raise RuntimeError(f"Logical q{logical} was scheduled too many times")
        self.assert_invariants()

    def reclaim_completed_logical(self, logical, measurement_by_logical, dag_has_remaining):
        if logical not in self.logical_to_physical:
            return
        if self.remaining_operations.get(logical, 0) != 0:
            return

        physical = self.logical_to_physical[logical]
        if dag_has_remaining:
            # REPRODUCTION DESIGN CHOICE: Phase 1 uses eager reclamation. A
            # logical qubit is measured if needed, reset, and returned only
            # after the physical qubit is safe as a fresh resource.
            self._emit_measurement_if_required(logical, physical, measurement_by_logical)
            self.output.reset(physical)
            del self.logical_to_physical[logical]
            self.physical_to_logical[physical] = None
            self.physical_fresh[physical] = True
            self.reuse_ready_from[physical] = logical
            self.completed_logicals.add(logical)
            self._refresh_free_state()
            event = {
                "logical": logical,
                "physical": physical,
                "reset": True,
                "dag_remaining": True,
            }
            self.reclaim_events.append(event)
            self.mapping_history.append({"event": "reclaim", **event})
        else:
            self._emit_measurement_if_required(logical, physical, measurement_by_logical)
            self.completed_logicals.add(logical)
        self.assert_invariants()

    def finalize_measurements(self, measurement_by_logical, measurement_order):
        for spec in sorted(measurement_order, key=lambda item: item.original_index):
            logical = spec.logical_qubit
            if logical in self.emitted_measurements:
                continue
            if logical not in self.logical_to_physical:
                if not self.physicalList:
                    raise RuntimeError(
                        f"No physical qubit available to preserve final measurement q{logical}"
                    )
                physical = self.physicalList[0]
                self.assign_logical(
                    logical,
                    physical,
                    reason="final-measurement-only logical",
                    node_id=None,
                )
            physical = self.logical_to_physical[logical]
            self._emit_measurement_if_required(logical, physical, measurement_by_logical)
        self.assert_measurements_preserved(measurement_by_logical)
        self.assert_invariants()

    def assert_measurements_preserved(self, measurement_by_logical):
        expected = set(measurement_by_logical)
        if self.emitted_measurements != expected:
            raise RuntimeError(
                "Original classical measurement destinations were not preserved: "
                f"expected logicals {sorted(expected)}, emitted "
                f"{sorted(self.emitted_measurements)}"
            )
        seen_classical = {}
        for event in self.measurement_events:
            classical = event["classical_bit"]
            if classical in seen_classical:
                raise RuntimeError(
                    f"Original measurement destination c{classical} was duplicated"
                )
            seen_classical[classical] = event

    def _emit_measurement_if_required(self, logical, physical, measurement_by_logical):
        spec = measurement_by_logical.get(logical)
        if spec is None or logical in self.emitted_measurements:
            return
        self.output.measure(physical, spec.classical_bit)
        self.emitted_measurements.add(logical)
        self.measurement_events.append(
            {
                "logical": logical,
                "physical": physical,
                "classical_bit": spec.classical_bit,
                "original_index": spec.original_index,
            }
        )

    def _refresh_free_state(self):
        self.physicalList = sorted(
            physical
            for physical, logical in self.physical_to_logical.items()
            if logical is None
        )
        for physical in range(self.device.num_qubits):
            self.physical_fresh[physical] = self.physical_to_logical[physical] is None

    def assert_invariants(self):
        if len(set(self.logical_to_physical.values())) != len(self.logical_to_physical):
            raise RuntimeError("A physical qubit hosts two live logical qubits")
        for logical, physical in self.logical_to_physical.items():
            if self.physical_to_logical[physical] != logical:
                raise RuntimeError("Mapping tables are inconsistent")
        for physical, logical in self.physical_to_logical.items():
            if logical is not None and self.logical_to_physical.get(logical) != physical:
                raise RuntimeError("Reverse mapping table is inconsistent")
        expected_free = sorted(
            physical
            for physical, logical in self.physical_to_logical.items()
            if logical is None
        )
        if self.physicalList != expected_free:
            raise RuntimeError(
                f"physicalList is stale: expected {expected_free}, got {self.physicalList}"
            )
        for physical in self.physicalList:
            if not self.physical_fresh[physical]:
                raise RuntimeError(
                    f"Physical qubit {physical} is free but not safe as a fresh resource"
                )
        for physical, logical in self.physical_to_logical.items():
            if logical is not None and self.reuse_ready_from.get(physical) is not None:
                raise RuntimeError(
                    f"Occupied physical qubit {physical} still has free-slot provenance"
                )
