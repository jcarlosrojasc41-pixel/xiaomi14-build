#!/usr/bin/env python3
"""Read-only preliminary host check for a fresh PixelOS source build.

Usage: python3 build-setup/check-host.py [existing-build-directory]
This checks the starting host, not device compatibility or source completeness.
"""

import argparse
import os
import platform
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    path = args.path.resolve()
    if not path.is_dir():
        parser.error(f"Build directory must already exist: {path}")

    blockers = []
    print(f"Build filesystem: {path}")
    print(f"Host: {platform.system()} {platform.machine()}")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        blockers.append("Use a Linux x86_64 build host.")

    free = shutil.disk_usage(path).free
    required = 400_000_000_000
    print(f"Free storage: {free / 1e9:.1f} GB ({free / 2**30:.1f} GiB)")
    print("Fresh checkout + build baseline: 400 GB free; extra space is useful.")
    if free < required:
        blockers.append(f"Free at least another {(required - free) / 1e9:.1f} GB.")
    if not os.access(path, os.W_OK):
        blockers.append("The selected build directory is not writable.")

    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        values = {
            line.split(":")[0]: int(line.split()[1]) * 1024
            for line in meminfo.read_text().splitlines()
            if line.startswith(("MemTotal:", "MemAvailable:", "SwapTotal:"))
        }
        print(f"Host RAM: {values['MemTotal'] / 2**30:.1f} GiB")
        print(f"Host available RAM: {values['MemAvailable'] / 2**30:.1f} GiB")
        print("Android recommends 64 GB RAM. Container limits must be checked separately.")
    print(f"Visible logical CPUs: {os.cpu_count()}")

    commands = (
        "git", "git-lfs", "repo", "python3", "make", "gcc", "g++", "bc",
        "bison", "flex", "gperf", "curl", "zip", "unzip", "xz", "rsync",
        "xmllint", "xsltproc",
    )
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        blockers.append("Missing command-line tools: " + ", ".join(missing))
    else:
        print("Basic command-line tools: present")

    print("\nThis is a preliminary check; development libraries and device sources are not validated.")
    if blockers:
        print("Preparation needed:")
        for blocker in blockers:
            print(f"- {blocker}")
        return 1
    print("Preliminary host checks passed. Validate the device source set before syncing/building.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
