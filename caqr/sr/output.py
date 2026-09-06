import json
from pathlib import Path


def write_sr_outputs(input_path, result, output_dir="output"):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    stem = Path(input_path).stem

    qasm_file = output_path / f"{stem}_sr.qasm"
    report_file = output_path / f"{stem}_sr_report.json"
    mapping_file = output_path / f"{stem}_sr_mapping.txt"

    with qasm_file.open("w") as file:
        file.write(result.circuit.qasm())
    with report_file.open("w") as file:
        json.dump(result.report, file, indent=2)
        file.write("\n")
    with mapping_file.open("w") as file:
        file.write("Mapping history\n")
        for event in result.report["mapping_history"]:
            file.write(json.dumps(event, sort_keys=True))
            file.write("\n")
        file.write("Reuse events\n")
        for event in result.report["reuse_events"]:
            file.write(json.dumps(event, sort_keys=True))
            file.write("\n")

    return {
        "qasm": str(qasm_file),
        "report": str(report_file),
        "mapping": str(mapping_file),
    }
