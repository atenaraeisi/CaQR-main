from dataclasses import dataclass

from caqr.sr.baseline import qiskit_sabre_baseline
from caqr.sr.critical_path import critical_frontier_ids
from caqr.sr.dag import preprocess_regular_circuit
from caqr.sr.mapping import choose_first_logical
from caqr.sr.mapping import select_physical_for_first_logical
from caqr.sr.mapping import select_physical_for_single_qubit_gate
from caqr.sr.mapping import select_physical_near_partner
from caqr.sr.metrics import metric_metadata
from caqr.sr.metrics import routed_stage_metrics
from caqr.sr.metrics import translated_stage_metrics
from caqr.sr.routing import route_until_adjacent
from caqr.sr.validation import assert_compiled_hardware_compliant
from caqr.sr.validation import count_two_qubit_operations


@dataclass
class SRCompilationResult:
    circuit: object
    report: dict


class DeadlockError(RuntimeError):
    pass


class SRCompiler:
    def __init__(self, circuit, device, baseline_seed=0):
        self.circuit = circuit
        self.device = device
        self.baseline_seed = baseline_seed
        self.dag = None
        self.measurement_by_logical = None
        self.measurement_order = None
        self.state = None

    def compile(self):
        from caqr.sr.state import SRState

        self.dag, self.measurement_by_logical, self.measurement_order = (
            preprocess_regular_circuit(self.circuit)
        )
        self.state = SRState.create(self.circuit, self.device, self.dag)

        while self.dag.has_remaining():
            frontier = self.dag.frontier()
            if not frontier:
                self._raise_deadlock("frontier is empty while DAG nodes remain")

            critical_ids = critical_frontier_ids(self.dag)
            scheduled = False
            for node in frontier:
                unmapped = [
                    logical
                    for logical in node.logical_qubits
                    if logical not in self.state.logical_to_physical
                ]
                if unmapped and node.node_id not in critical_ids:
                    self.state.mapping_history.append(
                        {
                            "event": "delay",
                            "node_id": node.node_id,
                            "reason": "non-critical frontier gate with unmapped operand",
                        }
                    )
                    continue

                self._ensure_mapped(node)
                if len(node.logical_qubits) == 2:
                    left, right = node.logical_qubits
                    route_until_adjacent(self.state, left, right, node.node_id)
                self._schedule(node)
                scheduled = True
                break

            if not scheduled:
                self._raise_deadlock("frontier processing made no progress")

        self.state.finalize_measurements(
            self.measurement_by_logical,
            self.measurement_order,
        )
        self._assert_all_nodes_scheduled()
        assert_compiled_hardware_compliant(self.state.output, self.device)
        report = self._build_report()
        return SRCompilationResult(self.state.output, report)

    def _ensure_mapped(self, node):
        unmapped = [
            logical
            for logical in node.logical_qubits
            if logical not in self.state.logical_to_physical
        ]
        if not unmapped:
            return

        if len(node.logical_qubits) == 1:
            logical = node.logical_qubits[0]
            physical = select_physical_for_single_qubit_gate(
                self.state,
                self.dag,
                logical,
            )
            self.state.assign_logical(
                logical,
                physical,
                reason="critical single-qubit gate",
                node_id=node.node_id,
            )
            return

        if len(unmapped) == 2:
            remaining_counts = self.dag.remaining_operations_per_logical()
            first = choose_first_logical(node.logical_qubits, remaining_counts)
            second = (
                node.logical_qubits[1]
                if node.logical_qubits[0] == first
                else node.logical_qubits[0]
            )
            first_physical = select_physical_for_first_logical(
                self.state,
                self.dag,
                first,
            )
            self.state.assign_logical(
                first,
                first_physical,
                reason="first operand of critical two-qubit gate",
                node_id=node.node_id,
            )
            second_physical = select_physical_near_partner(
                self.state,
                first_physical,
            )
            self.state.assign_logical(
                second,
                second_physical,
                reason=f"near mapped partner q{first}",
                node_id=node.node_id,
            )
            return

        if len(unmapped) == 1:
            logical = unmapped[0]
            partner = [
                item for item in node.logical_qubits if item != logical
            ][0]
            partner_physical = self.state.logical_to_physical[partner]
            physical = select_physical_near_partner(self.state, partner_physical)
            self.state.assign_logical(
                logical,
                physical,
                reason=f"near mapped partner q{partner}",
                node_id=node.node_id,
            )

    def _schedule(self, node):
        self.state.append_operation(node)
        self.dag.remove(node.node_id)
        dag_has_remaining = self.dag.has_remaining()
        for logical in sorted(set(node.logical_qubits)):
            self.state.reclaim_completed_logical(
                logical,
                self.measurement_by_logical,
                dag_has_remaining,
            )

    def _build_report(self):
        final_two_qubit_count = count_two_qubit_operations(self.state.output)
        original_two_qubit_count = sum(
            1 for node in self.dag.nodes if len(node.logical_qubits) == 2
        )
        reused_previous_logicals = {
            event["previous_logical"] for event in self.state.reuse_events
        }
        reclaimed_but_never_reused = [
            event
            for event in self.state.reclaim_events
            if event["logical"] not in reused_previous_logicals
        ]
        sr_pre_basis = routed_stage_metrics(
            self.state.output,
            routed_two_qubit_operation_count=self.state.routed_two_qubit_operation_count,
        )
        sr_post_basis = translated_stage_metrics(self.state.output)
        report = {
            "mode": "sr",
            "logical_qubits": self.circuit.num_qubits,
            "original_logical_width": self.circuit.num_qubits,
            "physical_qubits_available": self.device.num_qubits,
            "physical_qubits_used": len(self.state.used_physical_qubits),
            "distinct_physical_qubits_used": sorted(self.state.used_physical_qubits),
            "reclaim_count": len(self.state.reclaim_events),
            "reuse_count": len(self.state.reuse_events),
            "reset_count": self.state.reset_count,
            "reclaimed_but_never_reused_count": len(reclaimed_but_never_reused),
            "reclaimed_but_never_reused": reclaimed_but_never_reused,
            "inserted_swap_count": self.state.inserted_swap_count,
            "swap_count": self.state.inserted_swap_count,
            "depth": self.state.output.depth(),
            "two_qubit_gate_count": final_two_qubit_count,
            "original_two_qubit_gate_count": original_two_qubit_count,
            "routed_two_qubit_operation_count": self.state.routed_two_qubit_operation_count,
            "basis_two_qubit_gate_count": sr_post_basis["basis_two_qubit_gate_count"],
            "translated_depth": sr_post_basis["translated_depth"],
            "metric_definitions": metric_metadata(self.device),
            "pre_basis": sr_pre_basis,
            "post_basis": sr_post_basis,
            "mapping_history": self.state.mapping_history,
            "reuse_events": self.state.reuse_events,
            "reclaim_events": self.state.reclaim_events,
            "swap_events": self.state.swap_events,
            "measurement_events": self.state.measurement_events,
            "qiskit_sabre_baseline": qiskit_sabre_baseline(
                self.circuit,
                self.device,
                seed=self.baseline_seed,
            ),
        }
        return report

    def _assert_all_nodes_scheduled(self):
        expected = set(node.node_id for node in self.dag.nodes)
        actual = set(self.state.scheduled_original_node_ids)
        if expected != actual:
            raise RuntimeError(
                "No logical operation may be lost or duplicated: "
                f"expected {sorted(expected)}, scheduled {sorted(actual)}"
            )
        if len(self.state.scheduled_original_node_ids) != len(actual):
            raise RuntimeError("A logical operation was scheduled more than once")
        if self.dag.has_remaining():
            raise RuntimeError(
                f"Compiled circuit terminated with remaining DAG nodes "
                f"{self.dag.unscheduled_node_ids()}"
            )

    def _raise_deadlock(self, reason):
        frontier = self.dag.frontier()
        critical_ids = critical_frontier_ids(self.dag)
        details = {
            "reason": reason,
            "frontier": [
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "logical_qubits": list(node.logical_qubits),
                }
                for node in frontier
            ],
            "critical_ids": sorted(critical_ids),
            "logical_to_physical": dict(self.state.logical_to_physical),
            "physical_to_logical": dict(self.state.physical_to_logical),
            "physicalList": list(self.state.physicalList),
            "remaining_nodes": self.dag.unscheduled_node_ids(),
        }
        raise DeadlockError(f"SR-CaQR deadlock: {details}")


def compile_regular_circuit(circuit, device, baseline_seed=0):
    return SRCompiler(circuit, device, baseline_seed=baseline_seed).compile()
