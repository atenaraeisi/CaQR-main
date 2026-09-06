import qiskit
from qiskit import transpile
from qiskit.transpiler import CouplingMap

from caqr.sr.metrics import POST_BASIS_GATES
from caqr.sr.metrics import PRE_BASIS_GATES
from caqr.sr.metrics import routed_stage_metrics
from caqr.sr.metrics import translated_stage_metrics


def qiskit_sabre_baseline(circuit, device, seed=0):
    try:
        transpiled = transpile(
            circuit,
            coupling_map=CouplingMap(couplinglist=device.directed_edges()),
            basis_gates=PRE_BASIS_GATES,
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
            "logical_qubits": circuit.num_qubits,
            "physical_qubits_available": device.num_qubits,
            "pre_basis_gates": list(PRE_BASIS_GATES),
            "post_basis_gates": list(POST_BASIS_GATES),
            "device": {
                "name": device.name,
                "num_qubits": device.num_qubits,
                "coupling_edges": [list(edge) for edge in device.directed_edges()],
            },
        }

    counts = transpiled.count_ops()
    pre_basis = routed_stage_metrics(transpiled)
    post_basis = translated_stage_metrics(transpiled)
    return {
        "status": "ok",
        "qiskit_version": qiskit.__version__,
        "routing_method": "sabre",
        "optimization_level": 3,
        "seed": seed,
        "logical_qubits": circuit.num_qubits,
        "physical_qubits_available": device.num_qubits,
        "pre_basis_gates": list(PRE_BASIS_GATES),
        "post_basis_gates": list(POST_BASIS_GATES),
        "device": {
            "name": device.name,
            "num_qubits": device.num_qubits,
            "coupling_edges": [list(edge) for edge in device.directed_edges()],
        },
        "swap_count": int(counts.get("swap", 0)),
        "depth": transpiled.depth(),
        "two_qubit_gate_count": pre_basis["two_qubit_operation_count"],
        "physical_qubits_used": len(pre_basis["distinct_physical_qubits_used"]),
        "distinct_physical_qubits_used": pre_basis["distinct_physical_qubits_used"],
        "pre_basis": pre_basis,
        "post_basis": post_basis,
    }
