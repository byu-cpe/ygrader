import sys
import shutil
import subprocess
import traceback


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
    print_color(TermColors.YELLOW, "Warning:", *msg)


def copy_all_files_in_dir(src_dir, dest, exts=None, exclude=[]):
    for f in src_dir.rglob("*"):
        if f.name in exclude:
            continue
        if exts is None or f.suffix in exts:
            print("Copying", f, "to", dest)
            shutil.copy(f, dest)


def check_file_exists(path):
    if not path.is_file():
        error(path, "does not exist")


def clang_format_code(dir_path):
    for f in dir_path.glob("*"):
        if f.suffix in (".c", ".h"):
            cmd = ["clang-format", "-i", f]
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # Run clang-format twice (this shouldn't be necessary, but I've run into it with one students code -- it would be considered a bug in clang)
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if p.returncode != 0:
                print(p.stdout)
                error("Clang format errored", str())


def names_to_dir(first_names, last_names, net_ids):
    return (
        first_names[0].replace(" ", "_") + "_" + last_names[0].replace(" ", "_") + "_" + net_ids[0]
    )


def hash_file(file_path):
    import sys
    import hashlib

    # BUF_SIZE is totally arbitrary, change for your app!
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

    md5 = hashlib.md5()
    sha1 = hashlib.sha1()

    with open(file_path, "rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)
            sha1.update(data)

    return md5.hexdigest()


class CallbackFailed(Exception):
    """Raise this exception (or subclass it and raise it) in your callback to indicate some failure, and skip to the next student."""

    pass


class WorkflowHashError(CallbackFailed):
    pass


def verify_workflow_hash(workflow_file_path, hash_str):

    if not workflow_file_path.is_file():
        error(workflow_file_path, "is missing")

    workflow_dir_path = workflow_file_path.parent
    if not (len(list(workflow_dir_path.glob("**/*"))) == 1):
        error(workflow_dir_path, "has more than one file")

    hash = hash_file(workflow_file_path)
    if hash != hash_str:
        raise WorkflowHashError


def ensure_tuple(x):
    """If x is not a list or tuple, convert to list"""
    if isinstance(x, tuple):
        return x
    elif isinstance(x, list):
        return tuple(x)
    else:
        return (x,)
