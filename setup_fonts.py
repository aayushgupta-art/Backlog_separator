import shutil
import sys
from pathlib import Path
import matplotlib

def setup_fonts() -> bool:
    source_dir = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
    target_dir = Path(__file__).parent / "fonts"
    target_dir.mkdir(parents=True, exist_ok=True)

    font_files = ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
    all_ok = True

    for font_name in font_files:
        src = source_dir / font_name
        dst = target_dir / font_name

        if not src.exists():
            print(f"Error: Source font not found: {src}")
            all_ok = False
            continue

        shutil.copy2(src, dst)
        size_bytes = dst.stat().st_size

        with open(dst, "rb") as f:
            header = f.read(4)

        size_kb = size_bytes / 1024
        header_hex = header.hex()
        is_size_valid = size_bytes > 100 * 1024
        is_header_valid = (header == b"\x00\x01\x00\x00")

        if is_size_valid and is_header_valid:
            print(f"Validated {font_name}: size = {size_kb:.1f} KB, header = {header_hex} [OK]")
        else:
            print(f"Validation FAILED for {font_name}: size = {size_kb:.1f} KB, header = {header_hex}")
            all_ok = False

    return all_ok

if __name__ == "__main__":
    success = setup_fonts()
    if not success:
        sys.exit(1)
