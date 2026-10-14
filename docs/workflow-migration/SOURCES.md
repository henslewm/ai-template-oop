# Pinned source provenance

Source: henslewm/universal-ai-project-template.
Commit: d6e582b7edeae24345a175f36639230726dbdead.
Destination base: a3dafc636054a85eeed6eaeb4c10e1fcb9d020a4.

The following files were exported from that Git commit, not the source working
tree. Their destination Git blob hashes match the pinned source exactly:

| File | Git blob |
| --- | --- |
| scripts/work_packet.py | 2b7a18394aa63b301545713ea2622a0575ca51ad |
| scripts/cli_exit.py | 8f2cb6dd19bde63d32abfa509d39016e49096217 |
| scripts/software_hardware.py | fa3d29487390750614f58d1b26d41a35008217fb |
| config/work-packet.schema.json | 335fc690a1dcebc028617d103b78edb2c5122a1f |
| config/domains/software-hardware.schema.json | 69aeda438e5002c1237f343e56b959c554698396 |
| examples/work-packets/software-hardware.contract.json | 4394cfa7f2ed24f1d74bf27d77e9a84dc097d902 |
| tests/test_work_packet.py | cc7b5b8f87d9223917f8c9d816fb1f082326d075 |
| requirements-work-packets.txt | 589d38521a92937b1bce05805414283fa39ba2dd |

The original packet parser keeps canonical hashes, history, transitions,
dependency verification, domain rules and risk/review floors. It passed its
42 original tests here unchanged.

software_hardware.py is a packet-validation dependency and its complete source
was preserved. Its acceptance-ledger status command is not available in this
destination because acceptance.py has not been migrated. No claim of a complete
hardware-controller migration is made.

Added workflow_scope.py and workflow_runtime.py wrap the preserved packet with
session exports and local ownership. They do not alter application ABCs,
canonical packet schema or lifecycle authority. Their SQLite database records
process ownership only; it is not a task, cost or acceptance ledger.

Routing, feedback, execution harness, metered launcher, acceptance, durable
project-wide state and safe closeout remain in the source repository, unchanged.
Their later adaptation remains separate work. Frozen source policies were not
copied into the destination. In particular, the donor closeout branch-deletion
behavior was not imported.

Runtime reference:
https://docs.docker.com/engine/containers/run/
https://docs.docker.com/engine/security/
Cline CLI installation reference:
https://github.com/cline/cline
