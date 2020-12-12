import pandas
import shutil
import subprocess
import sys

from . import utils

from .utils import error, print_color, TermColors

# from .paths import repos_path, code_checker_path, root_path


# def get_students(csv_path):
#     # Read CSV
#     if not csv_path.is_file():
#         error("CSV file", csv_path, "does not exist.")
#     df = pandas.read_csv(csv_path)
#     if df.columns[0] != "Last Name":
#         error("Column 0 of CSV should be 'Last Name', but it is", df.columns[0])
#     if df.columns[1] != "First Name":
#         error("Column 1 of CSV should be 'First Name', but it is", df.columns[1])
#     if df.columns[2] != "Net ID":
#         error("Column 2 of CSV should be 'Net ID', but it is", df.columns[2])
#     if df.columns[3] != "Github username":
#         error("Column 3 of CSV should be 'Github username', but it is", df.columns[3])
#     print_color(TermColors.PURPLE, "There are", len(df.index), "students in csv file.")

#     # Filter by students who have a github username
#     df = df[df["Github username"].notnull()]

#     return df


# def create_repos_dir(force):
#     # Create student repos dir, deleting first if needed
#     if repos_path.is_dir():
#         if not force:
#             error(
#                 "Student repo directory,",
#                 repos_path,
#                 ", already exists.  Please delete or use the --force option.",
#             )
#         else:
#             print_color(
#                 TermColors.YELLOW,
#                 "Deleting existing student repo directory,",
#                 repos_path,
#             )
#             shutil.rmtree(str(repos_path))

#     print_color(TermColors.GREEN, "Creating student repo directory,", repos_path)
#     repos_path.mkdir()


def clone_repo(git_path, tag, student_repo_path):
    if student_repo_path.is_dir():
        print_color(
            TermColors.BLUE,
            "Student repo",
            student_repo_path.name,
            "already cloned. Running git pull",
        )
        cmd = ["git", "pull"]
        p = subprocess.run(cmd)
        if p.returncode:
            print_color(TermColors.RED, "git pull failed")
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
