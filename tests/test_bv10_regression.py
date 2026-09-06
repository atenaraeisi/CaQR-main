import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
EXPECTED_STDOUT = "We reuse 8 qubits, and now a total of 2 logical qubits are used."


class BV10RegressionTest(unittest.TestCase):
    def run_in_temp_repo(self, args):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            for filename in [
                "main.py",
                "circuit_analysis.py",
                "quantum_utils.py",
                "validate.py",
            ]:
                shutil.copy2(ROOT / filename, workdir / filename)

            shutil.copytree(ROOT / "caqr", workdir / "caqr")
            (workdir / "benchmarks").mkdir()
            (workdir / "output").mkdir()
            shutil.copy2(ROOT / "benchmarks" / "bv_n10.qasm", workdir / "benchmarks" / "bv_n10.qasm")
            shutil.copy2(ROOT / "benchmarks" / "qelib1.inc", workdir / "benchmarks" / "qelib1.inc")

            result = subprocess.run(
                [sys.executable, "main.py"] + args,
                cwd=workdir,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), EXPECTED_STDOUT)

            self.assert_golden_file(workdir, "bv_n10_reuse_chain.txt")
            self.assert_golden_file(workdir, "bv_n10_reuse_map.txt")
            self.assert_golden_file(workdir, "bv_n10_reuse.qasm")

            validate = subprocess.run(
                [sys.executable, "validate.py", "bv_n10"],
                cwd=workdir,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertEqual(validate.stdout.strip(), "Validation passed")

    def assert_golden_file(self, workdir, filename):
        actual = (workdir / "output" / filename).read_text()
        expected = (GOLDEN / filename).read_text()
        self.assertEqual(actual, expected)

    def test_default_cli_preserves_bv10_behavior(self):
        self.run_in_temp_repo(["-b", "benchmarks/bv_n10.qasm", "-v", "0"])

    def test_explicit_qs_cli_preserves_bv10_behavior(self):
        self.run_in_temp_repo(["--mode", "qs", "-b", "benchmarks/bv_n10.qasm", "-v", "0"])

    def test_sr_mode_is_not_implemented(self):
        result = subprocess.run(
            [
                sys.executable,
                "main.py",
                "--mode",
                "sr",
                "-b",
                "benchmarks/bv_n10.qasm",
                "--device",
                "fake_device",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SR-CaQR is not implemented yet", result.stderr)


if __name__ == "__main__":
    unittest.main()
