"""
Fix ctranslate2 CUDA library issues on Linux kernel 6.6+ / CUDA 12 environments.

Two problems fixed here:

1. execstack — ctranslate2 4.x ships libctranslate2.so with GNU_STACK marked
   RWE; Linux kernel 6.6+ refuses to load it.  Fixed by clearing the PF_X
   bit from the PT_GNU_STACK segment in the ELF header.

2. cuDNN 8 sub-libraries missing — ctranslate2 4.x bundles a *consolidated*
   cuDNN 8.9.7 (all ops in one .so) but cuDNN 8's runtime loader still tries
   to dlopen the historical sub-library names (libcudnn_ops_infer.so.8, etc.).
   Fixed by creating symlinks for each sub-library name pointing at the
   bundled consolidated library.

Run once after every `uv sync`:

    uv run python scripts/fix_cuda_libs.py

No system tools required — uses only Python stdlib.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

# ── ELF64 execstack constants ─────────────────────────────────────────────────
_MAGIC = b"\x7fELF"
_ELFCLASS64 = 2
_PT_GNU_STACK = 0x6474E551
_PF_X = 0x1

# cuDNN 8 sub-library names that the consolidated .so tries to dlopen
_CUDNN8_SUB_LIBS = [
    "libcudnn_ops_infer.so.8",
    "libcudnn_ops_train.so.8",
    "libcudnn_cnn_infer.so.8",
    "libcudnn_cnn_train.so.8",
    "libcudnn_adv_infer.so.8",
    "libcudnn_adv_train.so.8",
]


def _clear_execstack(path: Path) -> bool:
    """Return True if the ELF was patched, False if already clean."""
    with open(path, "r+b") as f:
        if f.read(4) != _MAGIC:
            return False
        if f.read(1)[0] != _ELFCLASS64:
            return False
        f.seek(0x20)
        (e_phoff,) = struct.unpack("<Q", f.read(8))
        f.seek(0x36)
        (e_phentsize,) = struct.unpack("<H", f.read(2))
        (e_phnum,) = struct.unpack("<H", f.read(2))
        for i in range(e_phnum):
            hdr_off = e_phoff + i * e_phentsize
            f.seek(hdr_off)
            (p_type,) = struct.unpack("<I", f.read(4))
            if p_type != _PT_GNU_STACK:
                continue
            (p_flags,) = struct.unpack("<I", f.read(4))
            if not (p_flags & _PF_X):
                return False
            f.seek(hdr_off + 4)
            f.write(struct.pack("<I", p_flags & ~_PF_X))
            return True
    return False


def _find_ctranslate2_libs_dir() -> Path | None:
    import site
    for sp in site.getsitepackages():
        d = Path(sp) / "ctranslate2.libs"
        if d.is_dir():
            return d
    return None


def _find_bundled_cudnn8(libs_dir: Path) -> Path | None:
    for p in libs_dir.glob("libcudnn-*.so.8.*"):
        if p.is_file() and not p.is_symlink():
            return p
    return None


def fix_execstack(libs_dir: Path) -> None:
    patched = 0
    for lib in libs_dir.iterdir():
        if not lib.is_file() or lib.is_symlink():
            continue
        try:
            if _clear_execstack(lib):
                print(f"  execstack patched: {lib.name}")
                patched += 1
        except PermissionError:
            print(f"❌  permission denied: {lib}  (try running as the file owner)")
            sys.exit(1)
        except Exception as exc:
            print(f"❌  {lib.name}: {exc}")
            sys.exit(1)
    if patched:
        print(f"  {patched} file(s) had execstack cleared.")
    else:
        print("  execstack: all files already clean.")


def fix_cudnn8_stubs(libs_dir: Path) -> None:
    # ctranslate2 4.4.x bundles a *consolidated* cuDNN 8 (all ops in one .so)
    # but its runtime still dlopen's the historical split-library names.
    # Symlinks back to the same file deadlock (glibc re-enters its own init mutex).
    # The fix: compile proper stub .so files that list the consolidated lib as a
    # NEEDED dep.  dlsym then finds all cuDNN symbols via the dep chain without
    # re-running any initialization.  Requires gcc (apt install build-essential).
    bundled = _find_bundled_cudnn8(libs_dir)
    if bundled is None:
        print("  cuDNN 8: no bundled cuDNN found — skipping stubs.")
        return
    import shutil, subprocess, tempfile
    if not shutil.which("gcc"):
        print("  cuDNN 8: gcc not found — install build-essential and re-run.")
        return
    created = 0
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write("/* empty stub — all symbols come from NEEDED dep below */\n")
        stub_src = f.name
    try:
        for name in _CUDNN8_SUB_LIBS:
            stub = libs_dir / name
            if stub.exists() and not stub.is_symlink():
                continue  # already a proper file (not symlink), skip
            if stub.is_symlink():
                stub.unlink()
            result = subprocess.run(
                [
                    "gcc", "-shared", "-fPIC", stub_src,
                    "-o", str(stub),
                    f"-Wl,-soname,{name}",
                    f"-Wl,-rpath,$ORIGIN",
                    f"-L{libs_dir}",
                    "-Wl,--no-as-needed",
                    f"-l:{bundled.name}",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"  gcc error for {name}: {result.stderr.strip()}")
                sys.exit(1)
            print(f"  cuDNN stub: {name} -> (links) {bundled.name}")
            created += 1
    finally:
        Path(stub_src).unlink(missing_ok=True)
    if created:
        print(f"  {created} stub(s) compiled.")
    else:
        print("  cuDNN 8 stubs: all already present.")


def main() -> None:
    libs_dir = _find_ctranslate2_libs_dir()
    if libs_dir is None:
        print("ctranslate2 not found — is it installed? (run: uv sync)")
        sys.exit(1)

    print(f"ctranslate2.libs: {libs_dir}")
    fix_execstack(libs_dir)
    fix_cudnn8_stubs(libs_dir)
    print("\nDone. ctranslate2 should now load correctly on CUDA 12 / kernel 6.6+.")


if __name__ == "__main__":
    main()
