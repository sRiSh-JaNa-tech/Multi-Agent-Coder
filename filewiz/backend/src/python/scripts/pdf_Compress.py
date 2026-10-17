import subprocess
import sys
import os
import shutil

def find_7zip():
    # 1. Environment variable
    env_path = os.environ.get("SEVEN_ZIP_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path

    # 2. PATH resolution
    for binary_name in ["7z", "7za"]:
        which_path = shutil.which(binary_name)
        if which_path:
            return which_path

    # 3. Check 7zip-bin npm package inside backend/node_modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))
    node_7zip_dir = os.path.join(project_root, "node_modules", "7zip-bin")

    platform_candidates = [
        os.path.join(node_7zip_dir, "win", "x64", "7za.exe"),
        os.path.join(node_7zip_dir, "win", "ia32", "7za.exe"),
        os.path.join(node_7zip_dir, "linux", "x64", "7za"),
        os.path.join(node_7zip_dir, "linux", "arm64", "7za"),
        os.path.join(node_7zip_dir, "linux", "ia32", "7za"),
        os.path.join(node_7zip_dir, "mac", "x64", "7za"),
        os.path.join(node_7zip_dir, "mac", "7za"),
    ]
    for candidate in platform_candidates:
        if os.path.isfile(candidate):
            return candidate

    # 4. Standard system install locations
    system_candidates = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        "/usr/bin/7z",
        "/usr/bin/7za",
        "/usr/local/bin/7z",
        "/usr/local/bin/7za",
    ]
    for candidate in system_candidates:
        if os.path.isfile(candidate):
            return candidate

    return None

def compress_pdf(input_pdf, output_path, level="normal"):
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"Input file not found: {input_pdf}")

    seven_zip_bin = find_7zip()
    if not seven_zip_bin:
        raise FileNotFoundError("7-Zip executable (7z or 7za) could not be located on the system.")

    # Remove existing output file if present so 7-Zip doesn't append to an old archive
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception as e:
            print(f"Warning: could not remove pre-existing output file: {e}")

    # Ensure parent output directory exists
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Base 7-Zip flags
    base_flags = [
        "a",         # Add files to archive
        "-t7z",      # 7z archive format
        "-y",        # Assume Yes on all queries
        "-mmt=on",   # Enable multi-threading
    ]

    # Compression level profiles
    if level == "low":
        compression_flags = [
            "-mx=1", # Fast compression
        ]
    elif level == "extreme":
        compression_flags = [
            "-mx=9",       # Ultra compression
            "-m0=lzma2",   # LZMA2 algorithm
            "-mfb=64",     # Fast bytes
            "-md=32m",     # Dictionary size
            "-ms=on",      # Solid archive
        ]
    else:  # normal
        compression_flags = [
            "-mx=5", # Normal compression
        ]

    command = [seven_zip_bin] + base_flags + compression_flags + [output_path, input_pdf]

    try:
        res = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
        if res.stdout:
            print(res.stdout)
        return True
    except subprocess.TimeoutExpired:
        print("Error: 7-Zip compression timed out after 120 seconds")
        return False
    except subprocess.CalledProcessError as e:
        print("7-Zip compression failed")
        if e.stdout:
            print("Stdout:", e.stdout)
        if e.stderr:
            print("Stderr:", e.stderr)
        return False


# CLI support
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("python pdf_Compress.py input.pdf output.7z [low|normal|extreme]")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_path = sys.argv[2]
    level = sys.argv[3].lower() if len(sys.argv) > 3 else "normal"

    success = compress_pdf(input_pdf, output_path, level)

    if success:
        print("PDF compressed successfully with 7-Zip")
        sys.exit(0)
    else:
        sys.exit(1)