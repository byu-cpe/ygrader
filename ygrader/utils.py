"""ygrader utility functions"""

import pathlib
import re
import sys
import shutil
import subprocess
import hashlib
import time
import os


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
                subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True
                )
                subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True
                )
            except subprocess.CalledProcessError as e:
                print(e.output)
                error("Clang format errored", str())


def names_to_dir(first_names, last_names, net_ids):
    """Convert first and last names to a valid filesystem directory name"""
    return (
        first_names[0].replace(" ", "_")
        + "_"
        + last_names[0].replace(" ", "_")
        + "_"
        + net_ids[0]
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
        raise WorkflowHashError(f"{workflow_file_path} is missing")

    workflow_dir_path = workflow_file_path.parent
    if len(list(workflow_dir_path.glob("**/*"))) != 1:
        raise WorkflowHashError(f"{workflow_dir_path} has more than one file")

    hash_val = hash_file(workflow_file_path)
    if hash_val != hash_str:
        raise WorkflowHashError(
            f"Workflow hash mismatch:\n  Got:      {hash_val}\n  Expected: {hash_str}"
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


def sanitize_filename(filename: str) -> str:
    """Replace invalid filename characters with underscores."""
    # Replace invalid characters with underscores
    # Invalid characters: < > : " / \ | ? *
    return re.sub(r'[<>:"/\\|?*]', "_", filename)


def is_wsl():
    """Check if running in WSL"""
    return (
        pathlib.Path("/proc/version").exists()
        and "microsoft"
        in pathlib.Path("/proc/version").read_text(encoding="utf-8").lower()
    )


# Track if we've already printed the focus warnings
_FOCUS_WARNING_PRINTED = False


def open_file_in_vscode(file_path, sleep_time=1.0):
    """Open a file in VS Code and return focus to terminal.

    Parameters
    ----------
    file_path: pathlib.Path or str
        Path to the file to open in VS Code
    sleep_time: float, optional
        Time in seconds to wait for VS Code to open before returning focus to terminal.
        Default is 1.0 seconds.
    """
    global _FOCUS_WARNING_PRINTED  # pylint: disable=global-statement

    file_path = pathlib.Path(file_path)

    # Verify file exists before trying to open
    if not file_path.exists():
        error(f"File does not exist: {file_path}")

    print(f"Opening {file_path} in VS Code...")

    # Open in VS Code (will steal focus)
    result = subprocess.run(
        ["code", "--reuse-window", file_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        error(f"VS Code exited with code {result.returncode}")

    # Check if we're in an SSH connection - if so, skip sending the key combination
    if os.environ.get("SSH_CONNECTION"):
        return

    # Give VS Code a moment to open, then send Ctrl+` to toggle terminal focus
    time.sleep(sleep_time)

    # Use AutoHotkey on WSL, osascript on macOS, xdotool on Linux
    if is_wsl():
        # Get the path to the .ahk file in the package
        package_dir = pathlib.Path(__file__).parent
        ahk_file = package_dir / "send_ctrl_backtick.ahk"
        autohotkey_path = pathlib.Path(
            "/mnt/c/Program Files/AutoHotkey/v2/AutoHotkey.exe"
        )

        if autohotkey_path.exists():
            result = subprocess.run([str(autohotkey_path), str(ahk_file)], check=False)
            if result.returncode != 0:
                if not _FOCUS_WARNING_PRINTED:
                    warning(
                        f"AutoHotkey failed to send hotkey (exit code {result.returncode}). Check that AutoHotkey v2 is properly installed."
                    )
                    _FOCUS_WARNING_PRINTED = True
        else:
            if not _FOCUS_WARNING_PRINTED:
                warning(
                    f"AutoHotkey not found at {autohotkey_path}. Install AutoHotkey v2 to keep terminal focus when opening files in VS Code."
                )
                _FOCUS_WARNING_PRINTED = True
    elif sys.platform == "darwin":
        # macOS: Use osascript to send Ctrl+` (toggle terminal) to VS Code
        applescript = """
            tell application "System Events"
                tell process "Code"
                    keystroke "`" using control down
                end tell
            end tell
        """
        result = subprocess.run(
            ["osascript", "-e", applescript],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            if not _FOCUS_WARNING_PRINTED:
                warning(
                    f"osascript failed to send hotkey (exit code {result.returncode}). "
                    "Make sure VS Code is granted accessibility permissions in System Preferences."
                )
                _FOCUS_WARNING_PRINTED = True
    else:
        # Check if xdotool exists
        try:
            subprocess.run(
                ["which", "xdotool"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            result = subprocess.run(["xdotool", "key", "ctrl+grave"], check=False)
            if result.returncode != 0:
                if not _FOCUS_WARNING_PRINTED:
                    warning(
                        f"xdotool failed to send hotkey (exit code {result.returncode}). Check that xdotool is properly installed."
                    )
                    _FOCUS_WARNING_PRINTED = True
        except subprocess.CalledProcessError:
            if not _FOCUS_WARNING_PRINTED:
                warning(
                    "xdotool not found. Install xdotool to keep terminal focus when opening files in VS Code."
                )
                _FOCUS_WARNING_PRINTED = True
