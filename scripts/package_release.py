from __future__ import annotations

import argparse
import hashlib
import tarfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.7.9"
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "__pycache__",
    "node_modules",
    "dist",
    ".venv",
}
EXCLUDED_PREFIXES = (
    Path("data/raw"),
    Path("data/external"),
    Path("artifacts/bench-evidence"),
    Path("runtime-data"),
)


def excluded(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS or part.startswith(".venv") for part in relative.parts):
        return True
    if relative.as_posix() == ".venv-path.txt":
        return True
    return any(relative == prefix or prefix in relative.parents for prefix in EXCLUDED_PREFIXES)


def release_files(*, include_manifest: bool = True) -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_dir() or excluded(path):
            continue
        if not include_manifest and path.relative_to(ROOT).as_posix() == "MANIFEST.sha256":
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest() -> Path:
    manifest = ROOT / "MANIFEST.sha256"
    lines = [
        f"{sha256(path)}  ./{path.relative_to(ROOT).as_posix()}"
        for path in release_files(include_manifest=False)
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def write_zip(output: Path) -> None:
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for path in release_files():
            archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))


def write_tar(output: Path) -> None:
    with tarfile.open(output, "w:gz", compresslevel=9) as archive:
        for path in release_files():
            archive.add(path, arcname=Path(ROOT.name) / path.relative_to(ROOT), recursive=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ForgeGuard Nexus release archives")
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent)
    args = parser.parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    write_manifest()
    cross_zip = output_dir / f"ForgeGuard-Nexus-5.0-v{VERSION}-Industrial-AI-Agent-Platform.zip"
    tar_path = output_dir / f"ForgeGuard-Nexus-5.0-v{VERSION}-Industrial-AI-Agent-Platform.tar.gz"
    windows_zip = output_dir / f"ForgeGuard-Nexus-5.0-v{VERSION}-Windows-x64.zip"
    checksum_path = output_dir / f"ForgeGuard-Nexus-5.0-v{VERSION}-SHA256SUMS.txt"

    write_zip(cross_zip)
    write_tar(tar_path)
    write_zip(windows_zip)

    outputs = [cross_zip, tar_path, windows_zip]
    checksum_path.write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in outputs) + "\n",
        encoding="utf-8",
    )
    for path in [*outputs, checksum_path]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
