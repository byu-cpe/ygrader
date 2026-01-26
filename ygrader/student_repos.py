"""Manages student repositories when using Github sumission system"""

import shutil
import subprocess
import sys
import re
import tempfile

from .utils import print_color, TermColors


def clone_repo(git_path, tag, student_repo_path, output=None):
    """Clone the student repository

    Args:
        git_path: URL to the git repository
        tag: Tag or branch to checkout
        student_repo_path: Path to clone into
        output: File handle to write output to (defaults to sys.stdout)

    Returns:
        True if successful, False otherwise
    """
    if output is None:
        output = sys.stdout

    # Track whether we're outputting to stdout (vs a log file)
    output_to_stdout = output is sys.stdout

    if student_repo_path.is_dir() and list(student_repo_path.iterdir()):
        return _fetch_and_checkout(student_repo_path, tag, output, output_to_stdout)

    return _clone_fresh(git_path, tag, student_repo_path, output, output_to_stdout)


def _fetch_and_checkout(student_repo_path, tag, output, output_to_stdout):
    """Fetch and checkout when repo already exists."""
    msg = f"Student repo {student_repo_path.name} already cloned. Re-fetching tag"
    if output_to_stdout:
        print_color(TermColors.BLUE, msg)
    else:
        print(msg, file=output)

    # Fetch
    cmd = ["git", "fetch", "--tags", "-f"]
    try:
        result = subprocess.run(
            cmd,
            cwd=student_repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, file=output, end="")
        if result.stderr:
            print(result.stderr, file=output, end="")
    except subprocess.CalledProcessError as e:
        msg = f"git fetch failed: {e}"
        if output_to_stdout:
            print_color(TermColors.RED, msg)
        else:
            print(msg, file=output)
        if e.stdout:
            print(e.stdout, file=output, end="")
        if e.stderr:
            print(e.stderr, file=output, end="")
        return False

    # Checkout tag
    if tag is None:
        # Get the default branch
        stdout = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
            cwd=student_repo_path,
            check=True,
            capture_output=True,
            universal_newlines=True,
        ).stdout
        tag = stdout.split("/")[1].strip()

    if tag not in ("master", "main"):
        tag = "tags/" + tag
    cmd = ["git", "checkout", tag, "-f"]
    try:
        result = subprocess.run(
            cmd,
            cwd=student_repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, file=output, end="")
        if result.stderr:
            print(result.stderr, file=output, end="")
    except subprocess.CalledProcessError as e:
        msg = f"git checkout of tag failed: {e}"
        if output_to_stdout:
            print_color(TermColors.RED, msg)
        else:
            print(msg, file=output)
        if e.stdout:
            print(e.stdout, file=output, end="")
        if e.stderr:
            print(e.stderr, file=output, end="")
        return False

    return True


def _clone_fresh(git_path, tag, student_repo_path, output, output_to_stdout):
    """Clone a fresh copy of the repo."""
    msg = f"Cloning repo, tag = {tag}"
    if output_to_stdout:
        print_color(TermColors.BLUE, msg)
    else:
        print(msg, file=output)

    if tag:
        cmd = [
            "git",
            "clone",
            "--branch",
            tag,
            git_path,
            str(student_repo_path.absolute()),
        ]
    else:
        cmd = ["git", "clone", git_path, str(student_repo_path.absolute())]

    # If output was explicitly provided (e.g., a log file), write directly to it.
    # Otherwise (stdout), redirect clone output to a temporary log file to keep terminal clean.
    if not output_to_stdout:
        return _clone_to_output(cmd, student_repo_path, output)

    return _clone_to_temp_log(cmd, student_repo_path)


def _clone_to_output(cmd, student_repo_path, output):
    """Clone and write output to the provided file handle."""
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, file=output, end="")
        if result.stderr:
            print(result.stderr, file=output, end="")
    except KeyboardInterrupt:
        shutil.rmtree(str(student_repo_path))
        sys.exit(-1)
    except subprocess.CalledProcessError as e:
        print("Clone failed", file=output)
        if e.stdout:
            print(e.stdout, file=output, end="")
        if e.stderr:
            print(e.stderr, file=output, end="")
        return False
    return True


def _clone_to_temp_log(cmd, student_repo_path):
    """Clone and write output to a temporary log file."""
    log_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, dir="/tmp", prefix="ygrader_clone_", suffix=".log"
        ) as tmp_log:
            log_path = tmp_log.name
            subprocess.run(cmd, check=True, stdout=tmp_log, stderr=subprocess.STDOUT)
        # Inform user where the clone output was written
        if log_path:
            print(f"git clone output logged to {log_path}")
    except KeyboardInterrupt:
        shutil.rmtree(str(student_repo_path))
        sys.exit(-1)
    except subprocess.CalledProcessError:
        print_color(TermColors.RED, "Clone failed")
        if log_path:
            print_color(TermColors.YELLOW, "See log:", log_path)
        return False
    return True


def convert_github_url_format(url, to_https):
    """ " Convert a github URL to either HTTPS or SSH format

    If to_https is True, URLs will be converted to https://github.com/org/repo format:

    >>> convert_github_url_format("git@github.com:byu-ecen123-classroom/123-labs-username01.git", True)
    'https://github.com/byu-ecen123-classroom/123-labs-username01'

    If to_https is False then SSH format is assumed, and URLs will be converted to git@github.com:org/repo format:

    >>> convert_github_url_format("https://github.com/byu-ecen123-classroom/123-labs-username01", False)
    'git@github.com:byu-ecen123-classroom/123-labs-username01.git'

    It also works if the student provides the repo with ".git" extension

    >>> convert_github_url_format("https://github.com/byu-ecen123-classroom/123-labs-username01.git", True)
    'https://github.com/byu-ecen123-classroom/123-labs-username01'

    Any invalid format is returned with modification:

    >>> convert_github_url_format("invalid format", True)
    'invalid format'

    """
    org = repo = None

    match = re.search(r"git@github\.com:(.*?)/(.*?).git", url)
    if match:
        org = match.group(1)
        repo = match.group(2)
    match = re.search(r"github\.com/(.*?)/(.*)", url)
    if match:
        org = match.group(1)
        repo = match.group(2)

    # Remove .git
    if repo is not None and repo.endswith(".git"):
        repo = repo[:-4]

    if org is not None:
        if to_https:
            return "https://github.com/" + org + "/" + repo
        return "git@github.com:" + org + "/" + repo + ".git"
    return url


def print_date(student_repo_path):
    """Print the last commit date to the repo"""
    print("Last commit: ")
    cmd = ["git", "log", "-1", r"--format=%cd"]
    subprocess.run(cmd, cwd=str(student_repo_path), check=False)
