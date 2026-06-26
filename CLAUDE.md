# CLAUDE.md — Project guidelines

## Git workflow

- **Never push directly to `master` or `main`.** All changes go through a feature branch and a pull request.
- **One issue → one feature branch → one PR.** Branch naming: `feature/<issue-number>-<short-slug>` (e.g. `feature/2-push-to-talk`).
- **Docs update with every PR.** If the PR adds or changes behaviour, update `README.md` (and any relevant module docstrings) in the same PR.

## Package management

- **Never install Python packages system-wide** — no `pip install`, no `sudo pip install`.
- All Python dependencies go through **uv**:
  - Add a dep: `uv add <package>` (inside `voice-paste/`)
  - Install everything: `uv sync --group dev`
  - Run the tool: `uv run voice-paste …`
- Torch/CUDA and other non-PyPI sources are declared in `[tool.uv.sources]` in `pyproject.toml`, not as one-off shell commands.
- System packages (`wl-clipboard`, `pipewire-bin`, `ffmpeg`, …) are documented in the README but **never installed automatically** by scripts or agents.

## Development approach

- **TDD.** Write failing tests first, then implement until they pass. No implementation without a corresponding test.
- Tests live in `voice-paste/tests/`. Run with `uv run pytest -v` from `voice-paste/`.

## Reference links

- Product spec: [`ubuntu_voice_paste_agent_task.md`](ubuntu_voice_paste_agent_task.md)
- GitHub issues / milestones:
  - [#1 — Epic v0.1 (clipboard-only CLI)](https://github.com/dremdem/push_to_terminal/issues/1)
  - [#2 — v0.2 push-to-talk](https://github.com/dremdem/push_to_terminal/issues/2)
  - [#3 — v0.3 auto-paste](https://github.com/dremdem/push_to_terminal/issues/3)
  - [#4 — v0.4 tray/GUI](https://github.com/dremdem/push_to_terminal/issues/4)
- uv docs: https://docs.astral.sh/uv/
- PyTorch CUDA wheels: https://download.pytorch.org/whl/cu124
- whisperx: https://github.com/m-bain/whisperX
- Wayland clipboard: `man wl-copy`
- PipeWire recording: `man pw-record`
