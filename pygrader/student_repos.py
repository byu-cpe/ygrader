import pandas
import shutil
import subprocess
import sys

from .utils import print_color, TermColors
from pygrader import utils


def clone_repo(git_path, tag, student_repo_path):
    if student_repo_path.is_dir() and list(student_repo_path.iterdir()):
        print_color(
            TermColors.BLUE,
            "Student repo",
            student_repo_path.name,
            "already cloned. Re-fetching tag",
        )

        # Fetch
        cmd = ["git", "fetch", "--tags", "-f"]
        p = subprocess.run(cmd, cwd=student_repo_path)
        if p.returncode:
            print_color(TermColors.RED, "git fetch failed")
            return False

        # Checkout tag
        cmd = ["git", "checkout", "tags/" + tag, "-f"]
        p = subprocess.run(cmd, cwd=student_repo_path)
        if p.returncode:
            print_color(TermColors.RED, "git checkout of tag failed")
            return False
        return True

    print_color(TermColors.BLUE, "Cloning repo, tag =", tag)
    cmd = [
        "git",
        "clone",
        "--branch",
        tag,
        git_path,
        str(student_repo_path.absolute()),
    ]
    try:
        p = subprocess.run(cmd)
    except KeyboardInterrupt:
        shutil.rmtree(str(student_repo_path))
        sys.exit(-1)
    if p.returncode:
        print_color(TermColors.RED, "Clone failed")
        return False
    return True


def print_date(student_repo_path):
    print("Last commit: ")
    cmd = ["git", "log", "-1", r"--format=%cd"]
    proc = subprocess.run(cmd, cwd=str(student_repo_path))
