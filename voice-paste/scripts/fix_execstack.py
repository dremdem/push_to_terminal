"""
Clear the execstack flag from ctranslate2 bundled shared libraries.

Needed on Linux kernel 6.6+ which enforces strict execstack restrictions.
ctranslate2 4.4.0 ships with GNU_STACK marked RWE; the kernel refuses to
load it with an "Invalid argument" error.

Run once after every `uv sync`:

    uv run python scripts/fix_execstack.py

No system tools required — uses Python struct to patch the ELF in-place.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

# ELF64 constants
_MAGIC = b"\x7fELF"
_ELFCLASS64 = 2
_PT_GNU_STACK = 0x6474E551
_PF_X = 0x1  # execute permission bit in p_flags


def _clear_execstack(path: Path) -> bool:
    """Return True if the file was patched, False if already clean."""
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
                return False  # already clean
            f.seek(hdr_off + 4)
            f.write(struct.pack("<I", p_flags & ~_PF_X))
            return True
    return False


def _find_ctranslate2_libs() -> list[Path]:
    import site

    dirs = [Path(p) for p in site.getsitepackages()]
    libs: list[Path] = []
    for d in dirs:
        libs.extend(d.glob("ctranslate2*/**/*.so*"))
    return [p for p in libs if p.is_file() and not p.is_symlink()]


def main() -> None:
    libs = _find_ctranslate2_libs()
    if not libs:
        print("ctranslate2 not found — is it installed? (run: uv sync)")
        sys.exit(1)

    patched = 0
    for lib in libs:
        try:
            if _clear_execstack(lib):
                print(f"✅  patched  {lib.name}")
                patched += 1
            else:
                print(f"   clean    {lib.name}")
        except PermissionError:
            print(f"❌  permission denied: {lib}  (try running as the file owner)")
            sys.exit(1)
        except Exception as exc:
            print(f"❌  {lib.name}: {exc}")
            sys.exit(1)

    if patched:
        print(f"\n{patched} file(s) patched. ctranslate2 should now load correctly.")
    else:
        print("\nAll libraries already clean — nothing to do.")


if __name__ == "__main__":
    main()
