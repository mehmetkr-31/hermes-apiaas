#!/usr/bin/env python3
import os
import subprocess
import pathlib
import sys


def patch_file(target_file, patch_file):
    print(f"Applying patch to {target_file}...")
    try:
        # -N: ignore patches that seem to be already applied
        # -p1: strip 1 path level (since we diffed absolute vs relative or similar)
        # Actually our diff used absolute paths for one side, but we should use -p1 if it's standard.
        # Let's check the patch header.

        cmd = ["patch", "-N", "-p1", str(target_file), str(patch_file)]
        # If -p1 doesn't work, try -p0
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully patched {target_file}")
        else:
            if (
                "previously applied" in result.stdout
                or "previously applied" in result.stderr
            ):
                print(f"Patch already applied to {target_file}")
            else:
                print(f"Error patching {target_file}: {result.stderr}")
                # Try -p0 as fallback
                cmd_p0 = ["patch", "-N", "-p0", str(target_file), str(patch_file)]
                result_p0 = subprocess.run(cmd_p0, capture_output=True, text=True)
                if result_p0.returncode == 0:
                    print(f"Successfully patched {target_file} (using -p0)")
                else:
                    print(f"Critical error patching {target_file}: {result_p0.stderr}")
                    sys.exit(1)
    except Exception as e:
        print(f"Failed to run patch command: {e}")
        sys.exit(1)


if __name__ == "__main__":
    AGENT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
    PATCH_DIR = AGENT_ROOT / "patches"

    # Identify target run_agent.py
    target_path = None

    # Check current venv site-packages
    import site

    site_packages = site.getsitepackages()
    for sp in site_packages:
        candidate = pathlib.Path(sp) / "run_agent.py"
        if candidate.exists():
            target_path = candidate
            break

    if not target_path:
        # Fallback for some venv setups
        import run_agent

        target_path = pathlib.Path(run_agent.__file__).resolve()

    patch_path = PATCH_DIR / "run_agent.py.patch"
    if patch_path.exists():
        patch_file(target_path, patch_path)
    else:
        print(f"Patch file not found at {patch_path}")

    # Copy minisweagent_path.py if it's missing from site-packages
    minisweagent_path_src = PATCH_DIR / "minisweagent_path.py"
    if minisweagent_path_src.exists() and target_path:
        site_packages_dir = target_path.parent
        minisweagent_path_dst = site_packages_dir / "minisweagent_path.py"
        print(f"Copying {minisweagent_path_src} to {minisweagent_path_dst}...")
        import shutil

        shutil.copy2(minisweagent_path_src, minisweagent_path_dst)
        print("Successfully copied minisweagent_path.py")
