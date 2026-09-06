import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from qiskit import ClassicalRegister
from qiskit import QuantumCircuit
from qiskit import QuantumRegister

from caqr.device import DeviceInfo
from caqr.modes.sr import run_sr_caqr
from caqr.sr.baseline import qiskit_sabre_baseline
from caqr.sr.compiler import DeadlockError
from caqr.sr.compiler import compile_regular_circuit
from caqr.sr.dag import UnsupportedCircuitError
from caqr.sr.dag import preprocess_regular_circuit
from caqr.sr.state import SRState
from caqr.sr.validation import assert_compiled_hardware_compliant


ROOT = Path(__file__).resolve().parents[1]


def line_device(num_qubits):
    edges = []
    for left in range(num_qubits - 1):
        right = left + 1
        edges.append((left, right))
        edges.append((right, left))
    return DeviceInfo(
        name=f"line_{num_qubits}",
        num_qubits=num_qubits,
        coupling_edges=edges,
    )


def disconnected_device():
    return DeviceInfo(
        name="disconnected_3",
        num_qubits=3,
        coupling_edges=[(0, 1), (1, 0)],
    )


def measured_circuit(num_qubits):
    qreg = QuantumRegister(num_qubits, "q")
    creg = ClassicalRegister(num_qubits, "c")
    return QuantumCircuit(qreg, creg)


def measurement_pairs(circuit):
    pairs = []
    for instruction, qargs, cargs in circuit.data:
        if instruction.name == "measure":
            pairs.append(
                (
                    circuit.find_bit(qargs[0]).index,
                    circuit.find_bit(cargs[0]).index,
                )
            )
    return pairs


class SRRegularTest(unittest.TestCase):
    def test_no_routing_required_on_line_topology(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(1, 2)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3))

        self.assertEqual(result.report["inserted_swap_count"], 0)
        self.assertEqual(result.report["original_two_qubit_gate_count"], 2)
        self.assertEqual(result.report["routed_two_qubit_operation_count"], 2)
        assert_compiled_hardware_compliant(result.circuit, line_device(3))

    def test_swap_required_and_routing_stops_when_adjacent(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(0, 2)
        circuit.cx(1, 2)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3))

        self.assertEqual(result.report["inserted_swap_count"], 1)
        self.assertEqual(len(result.report["swap_events"]), 1)
        self.assertEqual(result.report["routed_two_qubit_operation_count"], 3)
        self.assertEqual(
            [instruction.name for instruction, _, _ in result.circuit.data].count("swap"),
            1,
        )
        assert_compiled_hardware_compliant(result.circuit, line_device(3))

    def test_occupied_to_occupied_swap_updates_mappings(self):
        circuit = measured_circuit(2)
        circuit.h(0)
        circuit.h(1)
        dag, _, _ = preprocess_regular_circuit(circuit)
        state = SRState.create(circuit, line_device(2), dag)
        state.assign_logical(0, 0, "test")
        state.assign_logical(1, 1, "test")

        state.apply_swap(0, 1, reason="unit-test")

        self.assertEqual(state.logical_to_physical[0], 1)
        self.assertEqual(state.logical_to_physical[1], 0)
        self.assertEqual(state.physical_to_logical[0], 1)
        self.assertEqual(state.physical_to_logical[1], 0)
        self.assertEqual(state.physicalList, [])

    def test_occupied_to_free_swap_moves_clean_free_slot(self):
        circuit = measured_circuit(1)
        circuit.h(0)
        dag, _, _ = preprocess_regular_circuit(circuit)
        state = SRState.create(circuit, line_device(2), dag)
        state.assign_logical(0, 0, "test")

        state.apply_swap(0, 1, reason="unit-test")

        self.assertEqual(state.logical_to_physical[0], 1)
        self.assertEqual(state.physical_to_logical[1], 0)
        self.assertIsNone(state.physical_to_logical[0])
        self.assertEqual(state.physicalList, [0])
        self.assertTrue(state.physical_fresh[0])

    def test_free_slot_after_swap_does_not_fake_reuse_event(self):
        circuit = measured_circuit(2)
        circuit.h(0)
        circuit.h(1)
        dag, _, _ = preprocess_regular_circuit(circuit)
        state = SRState.create(circuit, line_device(2), dag)
        state.assign_logical(0, 0, "test")
        state.apply_swap(0, 1, reason="unit-test")

        state.assign_logical(1, 0, "fresh slot after swap")

        self.assertEqual(state.logical_to_physical[0], 1)
        self.assertEqual(state.logical_to_physical[1], 0)
        self.assertEqual(state.reuse_events, [])

    def test_reclaimed_free_location_can_be_used_by_swap(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(0, 2)
        circuit.cx(1, 2)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3))

        self.assertEqual(result.report["reuse_count"], 0)
        self.assertEqual(result.report["reclaim_count"], 1)
        self.assertEqual(result.report["reset_count"], 1)
        self.assertEqual(result.report["reclaimed_but_never_reused_count"], 1)
        self.assertEqual(result.report["inserted_swap_count"], 1)
        self.assertIsNone(result.report["swap_events"][0]["owner_right_before"])

    def test_multiple_consecutive_ownership_changes_one_physical(self):
        circuit = measured_circuit(4)
        circuit.cx(0, 1)
        circuit.cx(2, 1)
        circuit.cx(3, 1)
        circuit.measure([0, 1, 2, 3], [0, 1, 2, 3])

        result = compile_regular_circuit(circuit, line_device(2))

        self.assertEqual(result.report["reuse_count"], 2)
        self.assertEqual(
            [
                (
                    event["physical"],
                    event["previous_logical"],
                    event["new_logical"],
                )
                for event in result.report["reuse_events"]
            ],
            [(1, 0, 2), (1, 2, 3)],
        )

    def test_logical_moved_by_swap_and_later_reclaimed(self):
        circuit = measured_circuit(4)
        circuit.cx(0, 1)
        circuit.cx(0, 1)
        circuit.cx(1, 2)
        circuit.cx(0, 3)
        circuit.measure([0, 1, 2, 3], [0, 1, 2, 3])

        result = compile_regular_circuit(circuit, line_device(3)).report
        swapped_logicals = set()
        for event in result["swap_events"]:
            for key in ["owner_left_before", "owner_right_before"]:
                if event[key] is not None:
                    swapped_logicals.add(event[key])
        reclaimed_logicals = {event["logical"] for event in result["reclaim_events"]}

        self.assertIn(1, swapped_logicals & reclaimed_logicals)

    def test_both_operands_moved_by_earlier_swaps_before_final_operation(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(1, 2)
        circuit.cx(0, 2)
        circuit.cx(0, 1)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3)).report
        self.assertEqual(result["inserted_swap_count"], 2)
        swapped_logicals = set()
        for event in result["swap_events"]:
            for key in ["owner_left_before", "owner_right_before"]:
                if event[key] is not None:
                    swapped_logicals.add(event[key])

        self.assertTrue({0, 1}.issubset(swapped_logicals))

    def test_reclamation_reuse_and_measurement_preservation(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(2, 1)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3))

        self.assertEqual(result.report["reuse_count"], 1)
        self.assertEqual(result.report["reuse_events"][0]["previous_logical"], 0)
        self.assertEqual(result.report["reuse_events"][0]["new_logical"], 2)
        self.assertIn(
            {"logical": 0, "physical": 0, "classical_bit": 0, "original_index": 2},
            result.report["measurement_events"],
        )
        self.assertEqual(sorted(measurement_pairs(result.circuit)), [(0, 0), (0, 2), (1, 1)])
        self.assertEqual(
            [instruction.name for instruction, _, _ in result.circuit.data].count("reset"),
            1,
        )

    def test_reclaimed_but_never_reused_reset_is_reported(self):
        circuit = measured_circuit(2)
        circuit.cx(0, 1)
        circuit.h(1)
        circuit.measure([0, 1], [0, 1])

        result = compile_regular_circuit(circuit, line_device(2)).report

        self.assertEqual(result["reclaim_count"], 1)
        self.assertEqual(result["reuse_count"], 0)
        self.assertEqual(result["reset_count"], 1)
        self.assertEqual(result["reclaimed_but_never_reused_count"], 1)

    def test_single_qubit_unmapped_frontier_uses_isolated_policy(self):
        circuit = measured_circuit(2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure([0, 1], [0, 1])

        result = compile_regular_circuit(circuit, line_device(3))
        first_map = [
            event
            for event in result.report["mapping_history"]
            if event["event"] == "map"
        ][0]

        self.assertEqual(first_map["logical"], 0)
        self.assertEqual(first_map["physical"], 1)
        self.assertEqual(first_map["reason"], "critical single-qubit gate")

    def test_unsupported_mid_circuit_measurement_is_rejected(self):
        circuit = measured_circuit(2)
        circuit.h(0)
        circuit.measure(0, 0)
        circuit.cx(0, 1)

        with self.assertRaisesRegex(UnsupportedCircuitError, "final measurements only"):
            compile_regular_circuit(circuit, line_device(2))

    def test_multiple_measurements_per_logical_is_rejected(self):
        circuit = measured_circuit(1)
        circuit.h(0)
        circuit.measure(0, 0)
        circuit.measure(0, 0)

        with self.assertRaisesRegex(UnsupportedCircuitError, "multiple measurements"):
            compile_regular_circuit(circuit, line_device(1))

    def test_disconnected_device_failure_is_explicit(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(0, 2)
        circuit.measure([0, 1, 2], [0, 1, 2])

        with self.assertRaisesRegex(ValueError, "No coupling path"):
            compile_regular_circuit(circuit, disconnected_device())

    def test_insufficient_physical_resources_is_explicit(self):
        circuit = measured_circuit(3)
        circuit.h(0)
        circuit.cx(1, 2)
        circuit.h(0)
        circuit.measure([0, 1, 2], [0, 1, 2])

        with self.assertRaisesRegex(RuntimeError, "No fresh physical qubit"):
            compile_regular_circuit(circuit, line_device(2))

    def test_frontier_no_schedulable_progress_raises_deadlock(self):
        circuit = measured_circuit(2)
        circuit.cx(0, 1)
        circuit.measure([0, 1], [0, 1])

        with patch("caqr.sr.compiler.critical_frontier_ids", return_value=set()):
            with self.assertRaisesRegex(DeadlockError, "frontier processing made no progress"):
                compile_regular_circuit(circuit, line_device(2))

    def test_circuit_with_unused_logical_qubits_preserves_measurements(self):
        circuit = measured_circuit(3)
        circuit.x(0)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3))

        self.assertEqual(
            sorted(event["classical_bit"] for event in result.report["measurement_events"]),
            [0, 1, 2],
        )
        self.assertEqual(result.report["logical_qubits"], 3)
        self.assertEqual(result.report["physical_qubits_available"], 3)

    def test_fig12_style_regular_fixture(self):
        circuit = measured_circuit(5)
        circuit.cx(1, 2)  # g1
        circuit.cx(0, 4)  # g2
        circuit.cx(3, 4)  # g3
        circuit.cx(1, 4)  # g4
        circuit.measure([0, 1, 2, 3, 4], [0, 1, 2, 3, 4])
        device = line_device(5)

        result = compile_regular_circuit(circuit, device)
        baseline = qiskit_sabre_baseline(circuit, device)

        self.assertEqual(result.report["inserted_swap_count"], 0)
        self.assertGreaterEqual(baseline["swap_count"], 1)
        self.assertGreaterEqual(result.report["reuse_count"], 1)
        assert_compiled_hardware_compliant(result.circuit, device)

    def test_metric_stages_do_not_conflate_swaps_with_basis_gates(self):
        circuit = measured_circuit(5)
        circuit.cx(1, 2)
        circuit.cx(0, 4)
        circuit.cx(3, 4)
        circuit.cx(1, 4)
        circuit.measure([0, 1, 2, 3, 4], [0, 1, 2, 3, 4])
        device = line_device(5)

        report = compile_regular_circuit(circuit, device).report
        baseline = report["qiskit_sabre_baseline"]

        self.assertIn("pre_basis", report)
        self.assertIn("post_basis", report)
        self.assertIn("pre_basis", baseline)
        self.assertIn("post_basis", baseline)
        self.assertEqual(baseline["pre_basis"]["swap_count"], 1)
        self.assertGreater(
            baseline["post_basis"]["basis_two_qubit_gate_count"],
            baseline["pre_basis"]["two_qubit_operation_count"],
        )
        self.assertEqual(report["physical_qubits_available"], 5)
        self.assertEqual(report["original_logical_width"], 5)
        self.assertIn("physical_qubits_used", baseline)

    def test_end_to_end_sr_compilation_from_qasm_and_device_json(self):
        circuit = measured_circuit(3)
        circuit.cx(0, 1)
        circuit.cx(2, 1)
        circuit.measure([0, 1, 2], [0, 1, 2])

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            qasm_path = tmp_path / "small_reuse.qasm"
            device_path = tmp_path / "line3.json"
            qasm_path.write_text(circuit.qasm())
            device_path.write_text(
                json.dumps(
                    {
                        "name": "line3",
                        "num_qubits": 3,
                        "coupling_edges": [[0, 1], [1, 0], [1, 2], [2, 1]],
                    }
                )
            )

            previous = Path.cwd()
            try:
                os.chdir(tmp_path)
                with redirect_stdout(StringIO()):
                    run_sr_caqr(str(qasm_path), str(device_path), verbose=0)
            finally:
                os.chdir(previous)

            report = json.loads((tmp_path / "output" / "small_reuse_sr_report.json").read_text())
            self.assertEqual(report["mode"], "sr")
            self.assertEqual(report["reuse_count"], 1)
            self.assertIn("qiskit_sabre_baseline", report)
            self.assertEqual(report["qiskit_sabre_baseline"]["routing_method"], "sabre")


if __name__ == "__main__":
    unittest.main()
