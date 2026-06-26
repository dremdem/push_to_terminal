# CLAUDE.md — Project guidelines

## Git workflow

- **Never push directly to `master` or `main`.** All changes go through a feature branch and a pull request.
- **One issue → one feature branch → one PR.** Branch naming: `feature/<issue-number>-<short-slug>` (e.g. `feature/2-push-to-talk`).
- **Docs update with every PR.** If the PR adds or changes behaviour, update `README.md` (and any relevant module docstrings) in the same PR.

## Development approach

- **TDD.** Write failing tests first, then implement until they pass. No implementation without a corresponding test.
- Tests live in `voice-paste/tests/`. Run with `pytest` from the `voice-paste/` directory.

## Reference links

- Product spec: [`ubuntu_voice_paste_agent_task.md`](ubuntu_voice_paste_agent_task.md)
- GitHub issues / milestones:
  - [#1 — Epic v0.1 (clipboard-only CLI)](https://github.com/dremdem/push_to_terminal/issues/1)
  - [#2 — v0.2 push-to-talk](https://github.com/dremdem/push_to_terminal/issues/2)
  - [#3 — v0.3 auto-paste](https://github.com/dremdem/push_to_terminal/issues/3)
  - [#4 — v0.4 tray/GUI](https://github.com/dremdem/push_to_terminal/issues/4)
- OpenAI Whisper API: https://platform.openai.com/docs/api-reference/audio
- Wayland clipboard: `man wl-copy`
- PipeWire recording: `man pw-record`
