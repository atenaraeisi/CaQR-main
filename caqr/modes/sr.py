from caqr.device import DeviceInfo
from caqr.sr.compiler import compile_regular_circuit
from caqr.sr.output import write_sr_outputs
from quantum_utils import get_circuit


def run_sr_caqr(input_argument, device=None, verbose=0):
    if device is None:
        raise ValueError("--device is required when running --mode sr")

    circuit = get_circuit(input_argument)
    device_info = DeviceInfo.from_json(device)
    result = compile_regular_circuit(circuit, device_info)
    output_paths = write_sr_outputs(input_argument, result)

    print(
        "SR-CaQR used "
        f"{result.report['physical_qubits_used']} physical qubits, "
        f"reused {result.report['reuse_count']} physical qubits, "
        f"and inserted {result.report['inserted_swap_count']} SWAPs."
    )
    if verbose > 0:
        print(f"QASM: {output_paths['qasm']}")
        print(f"Report: {output_paths['report']}")
        print(f"Mapping: {output_paths['mapping']}")
