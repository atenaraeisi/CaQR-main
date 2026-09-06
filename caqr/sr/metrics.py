import qiskit
from qiskit import transpile

from caqr.sr.validation import count_two_qubit_operations


PRE_BASIS_GATES = ["u1", "u2", "u3", "cx", "swap", "measure", "reset"]
POST_BASIS_GATES = ["u1", "u2", "u3", "cx", "measure", "reset"]


def operation_names(circuit):
    return [instruction.name for instruction, _, _ in circuit.data]


def distinct_physical_qubits_used(circuit):
    used = set()
    for instruction, qargs, _ in circuit.data:
        if instruction.name == "barrier":
            continue
        for qubit in qargs:
            used.add(circuit.find_bit(qubit).index)
    return sorted(used)


def routed_stage_metrics(circuit, routed_two_qubit_operation_count=None):
    counts = circuit.count_ops()
    metrics = {
        "swap_count": int(counts.get("swap", 0)),
        "depth": circuit.depth(),
        "two_qubit_operation_count": count_two_qubit_operations(circuit),
        "distinct_physical_qubits_used": distinct_physical_qubits_used(circuit),
    }
    if routed_two_qubit_operation_count is not None:
        metrics["routed_two_qubit_operation_count"] = routed_two_qubit_operation_count
    return metrics


def translate_to_post_basis(circuit):
    # REPRODUCTION DESIGN CHOICE: Basis-stage metrics decompose routed circuits
    # to a common u1/u2/u3/cx/measure/reset gate set with optimization disabled,
    # so one logical SWAP is not conflated with one hardware two-qubit gate.
    return transpile(
        circuit,
        basis_gates=POST_BASIS_GATES,
        optimization_level=0,
    )


def translated_stage_metrics(circuit):
    translated = translate_to_post_basis(circuit)
    return {
        "basis_gates": list(POST_BASIS_GATES),
        "basis_two_qubit_gate_count": count_two_qubit_operations(translated),
        "translated_depth": translated.depth(),
        "counts": dict(translated.count_ops()),
    }


def metric_metadata(device):
    return {
        "qiskit_version": qiskit.__version__,
        "pre_basis_gates": list(PRE_BASIS_GATES),
        "post_basis_gates": list(POST_BASIS_GATES),
        "device": {
            "name": device.name,
            "num_qubits": device.num_qubits,
            "coupling_edges": [list(edge) for edge in device.directed_edges()],
        },
    }
