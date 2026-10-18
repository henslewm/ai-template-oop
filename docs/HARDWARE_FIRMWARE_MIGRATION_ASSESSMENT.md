# Hardware/firmware verification migration assessment

Compared with `henslewm/universal-ai-project-template` at
`d6e582b7edeae24345a175f36639230726dbdead`, inspected 2026-10-18. “Present”
means the destination has the corresponding file; it does not imply that the
donor behavior is integrated or that physical hardware was tested.

| Donor control | Destination comparison | Finding |
| --- | --- | --- |
| `scripts/software_hardware.py` | Same path; its destination blob is `fa3d29487390750614f58d1b26d41b1a35008217fb`, matching the pinned donor. | Domain validation, evidence-record validation, digest binding, and status derivation logic are present. Its `status` path expects the donor acceptance API (`replay`, `deterministic_status`, and artifact identity); destination `scripts/acceptance.py` instead uses `load(journal, task_stream)` and does not expose those APIs. Status derivation is therefore not integrated with the destination acceptance journal. |
| `DOMAIN_PROFILE.md` | No destination equivalent was found. | Missing profile guidance: hardware orientation/startup, component decomposition, verification ladder procedure, firmware/build guidance, and physical-intervention boundary. The destination schema still refers to the absent `templates/software-hardware/PROFILE.md`. |
| `config/domains/software-hardware.schema.json` | Same path; destination blob `69aeda438e5002c1237f343e56b959c554698396` matches the pinned donor. | Contract-domain and structured hardware-evidence schemas are present. |
| `scripts/acceptance.py` hardware controls | Destination has an acceptance controller, but its `ATTESTATION` branch raises “Hardware evidence ingestion is not enabled”; `acceptance_runtime.prepare_check` refuses a commandless hardware/manual check as `UNVERIFIED`. | Donor hardware attestation and ledger integration are not migrated into the destination controller. This assessment does not enable physical evidence ingestion. |
| `scripts/validate_bootstrap.py` profile intake control | No destination counterpart was found; `tools/project_intake.py` explicitly says it does not imply hardware verification. | Donor's required hardware-orientation intake gate is missing. |
| `tests/test_software_hardware.py` | No destination counterpart. The donor suite contains 50 test methods. | Dedicated domain, attestation, evidence-record, status, and example-suite coverage was absent. This change adds a focused offline gate test, not the donor suite wholesale. |
| `examples/software-hardware/README.md` | No corresponding destination file. | Missing decomposition guide and operator procedure. |
| `examples/software-hardware/hardware-evidence.example.json` | No corresponding destination file. | Missing illustrative record (not real hardware evidence). |
| `examples/software-hardware/packets/SHB-01-codec.contract.json` | No corresponding destination file. | Missing codec packet from the worked decomposition. |
| `examples/software-hardware/packets/SHB-02-transport.contract.json` | No corresponding destination file. | Missing transport packet. |
| `examples/software-hardware/packets/SHB-03-device.contract.json` | No corresponding destination file. | Missing device-abstraction packet. |
| `examples/software-hardware/packets/SHB-04-adapter.contract.json` | No corresponding destination file. | Missing hardware-adapter packet with a hardware-in-loop rung. |
| `examples/software-hardware/packets/SHB-05-telemetry.contract.json` | No corresponding destination file. | Missing telemetry packet. |
| `examples/software-hardware/packets/SHB-06-workflow.contract.json` | No corresponding destination file. | Missing field-workflow packet. |
| `examples/software-hardware/sample/synth_bridge/__init__.py` | No corresponding destination file. | Missing sample package initializer. |
| `examples/software-hardware/sample/synth_bridge/adapter.py` | No corresponding destination file. | Missing synthetic hardware adapter example. |
| `examples/software-hardware/sample/synth_bridge/codec.py` | No corresponding destination file. | Missing synthetic protocol codec example. |
| `examples/software-hardware/sample/synth_bridge/device.py` | No corresponding destination file. | Missing device-abstraction example. |
| `examples/software-hardware/sample/synth_bridge/fake_device.py` | No corresponding destination file. | Missing fake-device test double. |
| `examples/software-hardware/sample/synth_bridge/telemetry.py` | No corresponding destination file. | Missing telemetry example. |
| `examples/software-hardware/sample/synth_bridge/transport.py` | No corresponding destination file. | Missing transport example. |
| `examples/software-hardware/sample/tests/__init__.py` | No corresponding destination file. | Missing sample test package initializer. |
| `examples/software-hardware/sample/tests/test_adapter.py` | No corresponding destination file. | Missing adapter verification tests. |
| `examples/software-hardware/sample/tests/test_codec.py` | No corresponding destination file. | Missing codec verification tests. |
| `examples/software-hardware/sample/tests/test_device.py` | No corresponding destination file. | Missing device verification tests. |
| `examples/software-hardware/sample/tests/test_integration.py` | No corresponding destination file. | Missing synthetic integration tests. |
| `examples/software-hardware/sample/tests/test_telemetry.py` | No corresponding destination file. | Missing telemetry verification tests. |
| `examples/software-hardware/sample/tests/test_transport.py` | No corresponding destination file. | Missing transport verification tests. |
| `examples/work-packets/software-hardware.contract.json` | Same donor file; destination blob `4394cfa7f2ed24f1d74bf27d77e9a84dc097d902`. | Only one synthetic codec packet is present; it covers fixture input and a machine rung, not a physical rung. |

## Offline exercise and evidence boundary

`tests/test_acceptance.py::test_synthetic_hardware_packet_stops_at_physical_gate_offline`
creates a synthetic hardware-domain packet, runs its unit check through the
disposable acceptance harness, then verifies that the hardware-in-loop rung
cannot be run as a command or attested through the destination controller. The
unit-check PASS is deterministic fixture evidence only. No hardware-evidence
record, real-device observation, firmware flash, hardware-in-loop test, or field
test is produced; the packet remains `UNVERIFIED_ON_HARDWARE`.

## Result

The schema, helper module, and one synthetic packet were transferred, but the
hardware/firmware track is **not fully migrated**: the profile and worked
decomposition are missing, the donor's dedicated test suite is absent, and
acceptance/status integration is incompatible with the destination controller.
This change adds one focused offline regression. Real hardware behavior remains
unverified; the test stops at the hardware gate rather than manufacturing
physical evidence or weakening the existing disabled-ingestion boundary.
