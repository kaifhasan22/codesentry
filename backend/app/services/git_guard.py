"""Trusted subprocess supervisor: never import or execute repository code.

Invoked with Python isolated mode. Survives Celery child termination long enough
(to the next poll) to kill Git and remove the orphaned workspace.
"""
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time


def usage(root, byte_limit, entry_limit):
    size = count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            count += 1
            try:
                info = os.lstat(Path(current) / name)
            except FileNotFoundError:
                continue  # Git atomically renames temporary pack/index files.
            if stat.S_ISREG(info.st_mode):
                size += info.st_size
            if size > byte_limit or count > entry_limit:
                return False
    return True


def main():
    root, timeout, byte_limit, entry_limit, url = sys.argv[1:]
    root = Path(root)
    parent = os.getppid()
    deadline = time.monotonic() + int(timeout)
    base = ["git", "-c", "core.hooksPath=/dev/null", "-c", "credential.helper=",
            "-c", "http.followRedirects=false", "-c", "protocol.allow=never",
            "-c", "protocol.https.allow=always", "-c", "core.symlinks=false"]
    # No checkout hooks, submodules, LFS or configured smudge filters. Git stores
    # symlinks as ordinary link-text files, never as operating-system links.
    commands = [base + ["clone", "--depth", "1", "--single-branch", "--no-tags", "--no-checkout", "--", url, str(root / 'source')],
                base + ["-C", str(root / 'source'), "checkout", "--force", "HEAD", "--", "."]]
    proc = None
    try:
        for command in commands:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True, cwd=root)
            while True:
                if os.getppid() != parent:
                    return 126
                if time.monotonic() >= deadline:
                    return 124
                if not usage(root, int(byte_limit), int(entry_limit)):
                    return 125
                result = proc.poll()
                if result is not None:
                    if result:
                        return 126
                    break
                time.sleep(0.2)
        return 0
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        if os.getppid() != parent:
            shutil.rmtree(root, ignore_errors=True)

if __name__ == '__main__':
    sys.exit(main())
