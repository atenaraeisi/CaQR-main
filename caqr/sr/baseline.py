import qiskit
from qiskit import transpile
from qiskit.transpiler import CouplingMap

from caqr.sr.validation import count_two_qubit_operations


def qiskit_sabre_baseline(circuit, device, seed=0):
    try:
        transpiled = transpile(
            circuit,
            coupling_map=CouplingMap(couplinglist=device.directed_edges()),
            optimization_level=3,
            routing_method="sabre",
            seed_transpiler=seed,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "qiskit_version": qiskit.__version__,
            "routing_method": "sabre",
            "optimization_level": 3,
            "seed": seed,
            "device": {
                "name": device.name,
                "num_qubits": device.num_qubits,
                "coupling_edges": [list(edge) for edge in device.directed_edges()],
            },
        }

    counts = transpiled.count_ops()
    return {
        "status": "ok",
        "qiskit_version": qiskit.__version__,
        "routing_method": "sabre",
        "optimization_level": 3,
        "seed": seed,
        "device": {
            "name": device.name,
            "num_qubits": device.num_qubits,
            "coupling_edges": [list(edge) for edge in device.directed_edges()],
        },
        "swap_count": int(counts.get("swap", 0)),
        "depth": transpiled.depth(),
        "two_qubit_gate_count": count_two_qubit_operations(transpiled),
    }
