""" ygrader utility functions"""
import pathlib
import sys
import shutil
import subprocess
import hashlib


class TermColors:
    """Terminal codes for printing in color"""

    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_color(color, *msg):
    """Print a message in color"""
    print(color + " ".join(str(item) for item in msg), TermColors.END)


def error(*msg, returncode=-1):
    """Print an error message and exit program"""
    print_color(TermColors.RED, "ERROR:", *msg)
    # print(traceback.print_stack())
    sys.exit(returncode)


def warning(*msg):
    """Print a warning message in yellow"""
    print_color(TermColors.YELLOW, "Warning:", *msg)


def copy_all_files_in_dir(src_dir, dest, exts=None, exclude=()):
    """Copy all files from src_dir to dest"""
    for path in src_dir.rglob("*"):
        if path.name in exclude:
            continue
        if exts is None or path.suffix in exts:
            print("Copying", path, "to", dest)
            shutil.copy(path, dest)


def check_file_exists(path):
    """Throw an error if a given file does not exist"""
    if not path.is_file():
        error(path, "does not exist")


def clang_format_code(dir_path):
    """Use clang to format all code in this path"""
    for path in dir_path.glob("*"):
        if path.suffix in (".c", ".h"):
            cmd = ["clang-format", "-i", path]
            try:
                # Run clang-format twice (this shouldn't be necessary, but I've run into it with one students code -- it would be considered a bug in clang)
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
            except subprocess.CalledProcessError as e:
                print(e.output)
                error("Clang format errored", str())


def names_to_dir(first_names, last_names, net_ids):
    """Convert first and last names to a valid filesystem directory name"""
    return (
        first_names[0].replace(" ", "_") + "_" + last_names[0].replace(" ", "_") + "_" + net_ids[0]
    )


def hash_file(file_path):
    """Returns a hash of a file"""

    buf_size = 65536  # lets read stuff in 64kb chunks!

    md5 = hashlib.md5()
    sha1 = hashlib.sha1()

    with open(file_path, "rb") as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            md5.update(data)
            sha1.update(data)

    return md5.hexdigest()


class CallbackFailed(Exception):
    """Raise this exception (or subclass it and raise it) in your callback to indicate some failure, and skip to the next student."""


class WorkflowHashError(CallbackFailed):
    """Error raised if the workflow file does not match."""


def verify_workflow_hash(workflow_file_path, hash_str):
    """Checks that the github workflow is valid (has 1 file and matches given hash)"""

    if not workflow_file_path.is_file():
        error(workflow_file_path, "is missing")

    workflow_dir_path = workflow_file_path.parent
    if len(list(workflow_dir_path.glob("**/*"))) != 1:
        error(workflow_dir_path, "has more than one file")

    hash_val = hash_file(workflow_file_path)
    if hash_val != hash_str:
        raise WorkflowHashError(
            f"Hash value {hash_val} does not match expected value of {hash_str}"
        )


def ensure_tuple(x):
    """If x is not a tuple, convert to tuple"""
    if isinstance(x, tuple):
        return x
    if isinstance(x, list):
        return tuple(x)
    return (x,)


def directory_is_empty(directory: pathlib.Path) -> bool:
    """Returns whether the given directory is empty"""
    return not any(directory.iterdir())
