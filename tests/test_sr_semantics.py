import unittest

from qiskit import BasicAer
from qiskit import ClassicalRegister
from qiskit import QuantumCircuit
from qiskit import QuantumRegister
from qiskit import execute

from caqr.device import DeviceInfo
from caqr.sr.compiler import compile_regular_circuit


DETERMINISTIC_SHOTS = 512
PROBABILISTIC_SHOTS = 20000
PROBABILISTIC_TOLERANCE = 0.05


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


def measured_circuit(num_qubits):
    qreg = QuantumRegister(num_qubits, "q")
    creg = ClassicalRegister(num_qubits, "c")
    return QuantumCircuit(qreg, creg)


class SRSemanticEquivalenceTest(unittest.TestCase):
    def assert_semantically_equivalent(
        self,
        original,
        device,
        shots=PROBABILISTIC_SHOTS,
        tolerance=PROBABILISTIC_TOLERANCE,
    ):
        compiled = compile_regular_circuit(original, device).circuit
        original_counts = self.run_counts(original, shots, seed=11)
        compiled_counts = self.run_counts(compiled, shots, seed=29)
        self.assert_distributions_close(original_counts, compiled_counts, shots, tolerance)

    def assert_deterministically_equivalent(self, original, device):
        compiled = compile_regular_circuit(original, device).circuit
        original_counts = self.run_counts(original, DETERMINISTIC_SHOTS, seed=11)
        compiled_counts = self.run_counts(compiled, DETERMINISTIC_SHOTS, seed=29)
        self.assertEqual(original_counts, compiled_counts)

    def run_counts(self, circuit, shots, seed):
        backend = BasicAer.get_backend("qasm_simulator")
        counts = execute(
            circuit,
            backend,
            shots=shots,
            seed_simulator=seed,
        ).result().get_counts()
        return {key.replace(" ", ""): value for key, value in counts.items()}

    def assert_distributions_close(self, left_counts, right_counts, shots, tolerance):
        for key in set(left_counts) | set(right_counts):
            left = left_counts.get(key, 0) / shots
            right = right_counts.get(key, 0) / shots
            self.assertLessEqual(
                abs(left - right),
                tolerance,
                f"{key}: original={left}, sr={right}",
            )

    def test_no_reuse_deterministic_outputs_match(self):
        circuit = measured_circuit(2)
        circuit.x(0)
        circuit.cx(0, 1)
        circuit.measure([0, 1], [0, 1])

        result = compile_regular_circuit(circuit, line_device(2)).report
        self.assertEqual(result["reuse_count"], 0)
        self.assert_deterministically_equivalent(circuit, line_device(2))

    def test_one_reuse_deterministic_outputs_match(self):
        circuit = measured_circuit(3)
        circuit.x(0)
        circuit.cx(0, 1)
        circuit.x(2)
        circuit.cx(2, 1)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3)).report
        self.assertEqual(result["reuse_count"], 1)
        self.assert_deterministically_equivalent(circuit, line_device(3))

    def test_multiple_reuse_probabilistic_outputs_match(self):
        circuit = measured_circuit(4)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.h(2)
        circuit.cx(2, 1)
        circuit.h(3)
        circuit.cx(3, 1)
        circuit.measure([0, 1, 2, 3], [0, 1, 2, 3])

        result = compile_regular_circuit(circuit, line_device(2)).report
        self.assertEqual(result["reuse_count"], 2)
        self.assert_semantically_equivalent(circuit, line_device(2))

    def test_swap_routing_probabilistic_outputs_match(self):
        circuit = measured_circuit(3)
        circuit.h(0)
        circuit.h(1)
        circuit.h(2)
        circuit.cx(0, 1)
        circuit.cx(0, 2)
        circuit.cx(1, 2)
        circuit.measure([0, 1, 2], [0, 1, 2])

        result = compile_regular_circuit(circuit, line_device(3)).report
        self.assertGreaterEqual(result["inserted_swap_count"], 1)
        self.assert_semantically_equivalent(circuit, line_device(3))

    def test_reuse_and_swap_probabilistic_outputs_match(self):
        circuit = measured_circuit(4)
        circuit.h(0)
        circuit.h(1)
        circuit.cx(0, 1)
        circuit.cx(0, 1)
        circuit.h(2)
        circuit.cx(1, 2)
        circuit.h(3)
        circuit.cx(0, 3)
        circuit.measure([0, 1, 2, 3], [0, 1, 2, 3])

        result = compile_regular_circuit(circuit, line_device(3)).report
        self.assertGreaterEqual(result["reuse_count"], 1)
        self.assertGreaterEqual(result["inserted_swap_count"], 1)
        self.assert_semantically_equivalent(circuit, line_device(3))


if __name__ == "__main__":
    unittest.main()
