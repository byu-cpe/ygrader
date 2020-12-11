import sys
import shutil
import subprocess


class TermColors:
    """ Terminal codes for printing in color """

    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_color(color, *msg):
    """ Print a message in color """
    print(color + " ".join(str(item) for item in msg), TermColors.END)


def error(*msg, returncode=-1):
    """ Print an error message and exit program """
    print_color(TermColors.RED, "ERROR:", *msg)
    sys.exit(returncode)


def copy_all_files_in_dir(src_dir, dest, exts=None):
    for f in src_dir.rglob("*"):
        if exts is None or f.suffix in exts:
            print("Copying", f, "to", dest)
            shutil.copy(f, dest)


def check_file_exists(path):
    if not path.is_file():
        error(path, "does not exist")


def clang_format_code(dir_path):
    print_color(TermColors.BLUE, "Formatting code in", dir_path)
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


def get_score(names, assignment_name, max_score, extra_message=""):
    if extra_message:
        print_color(TermColors.BOLD, extra_message)
    input_txt = (
        TermColors.YELLOW
        + "Enter score for "
        + names
        + ", "
        + (assignment_name + ":")
        + (" (0-" + str(max_score) + "), ")
    )
    input_txt += (
        "'s' to skip, 'r' to retry (w/ rebuild), or 't' to do a test re-run (w/o rebuild):"
        + TermColors.END
    )

    while True:
        txt = input(input_txt)
        if txt in ["s", "r", "t"]:
            return txt
        else:
            if not txt.isdigit():
                print("Invalid input. Try again.")
                continue
            score = int(txt)
            if 0 <= score <= max_score:
                return score
            else:
                print("  Invalid input. Try again.")
