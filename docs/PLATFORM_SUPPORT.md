# Platform support and onboarding decisions

Decision record for [issue #18](https://github.com/henslewm/ai-template-oop/issues/18),
2026-10-18, under the owner's instruction to settle the #18 decisions and continue.

## Supported baseline

- Windows, PowerShell 5.1 or PowerShell 7, and Python 3.12+ are the supported
  local workflow baseline. Verification for this record uses Python 3.12;
  another version requires its applicable checks.
- Python 3.11 collection is unverified and is not a release requirement. Even a
  successful collection would not establish Windows workflow support: the scope
  and journal implementations explicitly require Python 3.12+ junction checks.
- The frozen `pyproject.toml` retains its `>=3.11` declaration. This decision
  establishes the supported workflow baseline without rewriting approval-bound
  metadata or claiming that the Windows workflow runs on 3.11.
- POSIX host onboarding is outside this release's supported host scope.

## Required clients and acceptance

Keep all client families already named in the original brief. A prepared
entrypoint or export is separate from a verified real-client onboarding result.

| Required target | Repository entrypoint | Acceptance observation |
| --- | --- | --- |
| Codex repository client | `AGENTS.md`, `MASTER_CODEX.md`, `.codex/` | A trusted repository session reads the correct rules and runs the offline foundation gate. |
| Claude Code | `CLAUDE.md`, `MASTER_CLAUDE_CODE.md`, `MASTER_INSTRUCTIONS.md` | A repository session explicitly reads the master files and runs the offline gate. |
| Mistral Vibe CLI | `AGENTS.md`, `.vibe/config.toml`, `MASTER_MISTRAL.md` | A trusted-folder session loads the rules; programmatic use follows the documented explicit agent choice. |
| GitHub Copilot | `.github/copilot-instructions.md` | The actual repository session reads the shared rules and task ownership. |
| ChatGPT web Project | `.chatgpt/`, `MASTER_CHATGPT.md` | Project instructions and uploaded/connected sources identify the correct repository revision. |
| Claude web Project | `.claude-web/`, `MASTER_CLAUDE.md` | Project instructions/knowledge identify the correct repository revision. |
| Mistral web Project | `.mistral/`, `MASTER_MISTRAL.md` | Project instructions/knowledge identify the correct repository revision. |

For this template, browser sessions analyse, review and hand off precise changes
to a repository client. Uploaded context does not transfer project activation or
pilot authority. A ChatGPT web Project uses uploaded or connected sources rather
than directly exposing a local folder; see
[official OpenAI documentation](https://learn.chatgpt.com/docs/projects).

## Web preparation and exit codes

From the repository root:

```powershell
python -B scripts/web_setup.py --client chatgpt
python -B scripts/web_setup.py --client claude
python -B scripts/web_setup.py --client mistral
```

Each command writes `.web-setup/web-setup-<client>.zip` and tries to copy that
client's instructions to the clipboard. Its output names the file to paste if
clipboard access is unavailable. Upload the files inside the archive using the
client's existing setup guide. This decision is included in all three file lists.

| Exit code | Meaning for `scripts/web_setup.py` |
| --- | --- |
| `0` | Archive prepared, with clipboard copy or a named paste-from-file fallback. |
| `1` | Explicit refusal for missing/unsafe listed inputs or an unsafe output destination. |
| `2` | Invalid CLI usage (`argparse`). |
| `130` | Interrupted; inspect existing output before retrying. |

Unexpected exceptions can also produce a nonzero exit and traceback; read the
diagnostic. Archive creation does not prove real-client onboarding. For local
checks use [the Windows quickstart](workflow-migration/WINDOWS_QUICKSTART.md).
GitHub CLI is required by the hosting/closeout steps that invoke it. Docker and
the verified worker image are required for worker execution.

## Reviewer permissions and remaining work

The reviewer's no-edit instructions are a work constraint. They do not prove a
separate filesystem boundary. Codex custom agents inherit the parent sandbox;
their `sandbox_mode` setting does not override the parent. An enforced read-only
review needs a parent session actually configured read-only. See
[official OpenAI documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents#approvals-and-sandbox-controls).

This records the disposition of PR #39's reviewer-permission claim. The tracked
`.codex` versus pilot-tree conflict remains [issue #48](https://github.com/henslewm/ai-template-oop/issues/48).

The target list and Python/host baseline are now decided. Keep #18 open for real
onboarding evidence for each required client: repository revision, client/version,
instruction-loading observation, applicable gate result and remaining limit.
Packaging tests, exported files and skipped bot reviews do not establish that
acceptance. This decision does not enable paid workers or change frozen approval.
