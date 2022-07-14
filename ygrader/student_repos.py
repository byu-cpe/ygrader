""" Manages student repositories when using Github sumission system """
import shutil
import subprocess
import sys
import re

from .utils import print_color, TermColors


def clone_repo(git_path, tag, student_repo_path):
    """Clone the student repository"""

    if student_repo_path.is_dir() and list(student_repo_path.iterdir()):
        print_color(
            TermColors.BLUE,
            "Student repo",
            student_repo_path.name,
            "already cloned. Re-fetching tag",
        )

        # Fetch
        cmd = ["git", "fetch", "--tags", "-f"]
        try:
            subprocess.run(cmd, cwd=student_repo_path, check=True)
        except subprocess.CalledProcessError:
            print_color(TermColors.RED, "git fetch failed")
            return False

        # Checkout tag
        if tag not in ("master", "main"):
            tag = "tags/" + tag
        cmd = ["git", "checkout", tag, "-f"]
        try:
            subprocess.run(cmd, cwd=student_repo_path, check=True)
        except subprocess.CalledProcessError:
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
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        shutil.rmtree(str(student_repo_path))
        sys.exit(-1)
    except subprocess.CalledProcessError:
        print_color(TermColors.RED, "Clone failed")
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
