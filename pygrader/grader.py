import pathlib
import enum
import sys
import csv
import zipfile
import time
import os
import shutil
import datetime
from typing import Callable
import inspect

import pandas

from . import grades_csv
from . import utils, student_repos

from .utils import CallbackFailed, print_color, TermColors, error, warning


class CodeSource(enum.Enum):
    """Used to indicate whether the student code is submitted via LearningSuite or Github"""

    LEARNING_SUITE = 1
    GITHUB = 2


class Grader:
    """Grader class"""

    def __init__(
        self,
        name: str,
        lab_name: str,
        grades_csv_path: pathlib.Path,
        grades_col_name: str,
        points: int,
        work_path: pathlib.Path = pathlib.Path.cwd(),
    ):
        self.name = name
        self.lab_name = lab_name

        self.grades_csv_path = pathlib.Path(grades_csv_path)

        # Listify grade_col_name and points
        # (Grader can grade multiple columns at once)
        if not isinstance(grades_col_name, (list, tuple)):
            grades_col_name = [grades_col_name]
        self.grades_col_names = grades_col_name
        if not isinstance(points, (list, tuple)):
            points = [points]
        self.points = points

        # Check that # of CSV columns to grade matches # of points list
        if len(self.grades_col_names) != len(self.points):
            error(
                "List length of 'grades_col_name'",
                "(" + str(len(self.grades_col_names)) + ")",
                "does not match length of 'points'",
                "(" + str(len(self.points)) + "). ",
            )

        # Make sure grades csv col names exist
        if not self.grades_csv_path.is_file():
            error("grades_csv_path", "(" + str(grades_csv_path) + ")", "does not exist")
        df = pandas.read_csv(self.grades_csv_path)
        for col_name in self.grades_col_names:
            if col_name not in df:
                error(
                    "Provided grade column name",
                    "(" + col_name + ")",
                    "does not exist in grades_csv_path",
                    "(" + str(self.grades_csv_path) + ")",
                )

        # Create a working directory
        self.work_path = pathlib.Path(work_path)
        self.work_path = self.work_path / (lab_name + "_" + name)

        # Initialize other class members
        self.code_source = None
        self.run_on_lab = None
        self.run_on_milestone = None
        self.groups_csv_path = None
        self.set_other_options()

    def set_callback_fcn(self, grading_fcn, prep_fcn=None):
        self.run_on_milestone = grading_fcn
        self.run_on_lab = prep_fcn

        callback_args = [
            "lab_name",
            "student_code_path",
            "run",
            "build",
            "first_names",
            "last_names",
            "net_ids",
        ]
        callback_args_optional = [
            "modified_time",
            "section",
            "homework_id",
        ]

        # Check that callback function(s) are valid
        callback_fcns = [grading_fcn]
        if prep_fcn:
            callback_fcns.append(prep_fcn)

        for callback_fcn in callback_fcns:
            argspec = inspect.getfullargspec(callback_fcn)

            # Check that kwargs is enabled
            if argspec.varkw is None:
                error(
                    "Your callback function",
                    "(" + callback_fcn.__name__ + ")",
                    "should accept keyward arguments (**kw). This is needed because the grader may provide different optional arguments to your callback depending on what data it has available",
                    "(" + ",".join(callback_args_optional) + ").",
                )

            # Check that all named arguments are valid
            for i, named_arg in enumerate(argspec.args):
                # Skip special arguments
                if named_arg in ("self", "cls") and i == 0:
                    continue
                if (named_arg not in callback_args) and (named_arg not in callback_args_optional):
                    error(
                        "Your callback function",
                        "(" + callback_fcn.__name__ + ")",
                        "takes a named argument",
                        "'" + named_arg + "'",
                        "but this is not provided by the grader. Please remove this argument or the grader will not be able to call your callback function correctly.",
                    )
                elif named_arg not in callback_args:
                    warning(
                        "Your callback function",
                        "(" + callback_fcn.__name__ + ")",
                        "takes a named argument",
                        "'" + named_arg + "'",
                        "but this argument is not always provided by the grader.",
                        "If it is missing from your grades CSV file this will cause a runtime error.",
                        "Please consider use keyword arguments (**kw) instead.",
                    )

    def set_submission_system_learning_suite(self, zip_path):
        self.code_source = CodeSource.LEARNING_SUITE
        self.learning_suite_submissions_zip_path = zip_path

        if not zip_path.is_file():
            error("Provided zip_path", zip_path, "does not exist")

    def set_submission_system_github(self, tag, github_url_csv_path, repo_col_name="github_url"):
        self.code_source = CodeSource.GITHUB
        self.github_csv_path = github_url_csv_path
        self.github_csv_col_name = repo_col_name
        self.github_tag = tag

        if not github_url_csv_path.is_file():
            error(
                "Provided github_url_csv_path",
                "(" + str(github_url_csv_path) + ")",
                "does not exist",
            )

        df = pandas.read_csv(github_url_csv_path)
        if repo_col_name not in df:
            error(
                "Provided repo_col_name",
                "(" + repo_col_name + ")",
                "is not a column in github_url_csv_path",
                "(" + str(github_url_csv_path) + ")",
            )

    def set_learning_suite_groups(self, csv_path, col_name="group"):
        if self.code_source != CodeSource.LEARNING_SUITE:
            error(
                "Please call set_submission_system_learning_suite() before calling set_learning_suite_groups()."
            )

        self.groups_csv_path = csv_path
        self.groups_csv_col_name = col_name

        if not csv_path.is_file():
            error("Provided groups csv_path", csv_path, "does not exist")

        df = pandas.read_csv(self.groups_csv_path)
        if col_name not in df:
            error("Provided groups col_name", col_name, "does not exist in", csv_path)

    def set_other_options(
        self,
        format_code=False,
        build_only=False,
        run_only=False,
        allow_rebuild=True,
        allow_rerun=True,
        help_msg="",
    ):
        self.format_code = format_code
        self.build_only = build_only
        self.run_only = run_only
        self.allow_rebuild = allow_rebuild
        self.allow_rerun = allow_rerun
        self.help_msg = help_msg

        if not (self.allow_rebuild or self.allow_rerun):
            error("At least one of allow_rebuild and allow_rerun needs to be True.")

        # If help message is a single string, duplicate to each milestone
        if isinstance(self.help_msg, str) or self.help_msg is None:
            self.help_msg = [self.help_msg] * len(self.grades_col_names)

    def validate_config(self):
        # Check that callback function has been set up
        if self.run_on_milestone is None:
            error(
                "Before calling run(), you must call set_callback_fcn() and provide a callback function to use for grading."
            )

        # Check that submission source is set
        if self.code_source is None:
            error(
                "Before calling run(), you must set a submission source by either calling set_submission_system_learning_suite() or set_submission_system_github()."
            )

    # def __init__(
    #     self,
    #     name: str,
    #     lab_name: str,
    #     points: list,
    #     work_path: pathlib.Path,
    #     code_source: CodeSource,
    #     grades_csv_path: pathlib.Path,
    #     grades_col_names: list,
    #     run_on_milestone: Callable[[str, pathlib.Path], None] = None,
    #     run_on_lab: Callable[[str, pathlib.Path], None] = None,
    #     github_csv_path: pathlib.Path = None,
    #     github_csv_col_name: str = None,
    #     github_tag: str = None,
    #     learning_suite_submissions_zip_path: pathlib.Path = None,
    #     learning_suite_groups_csv_path: pathlib.Path = None,
    #     learning_suite_groups_csv_col_name: str = None,
    #     format_code: bool = False,
    #     build_only: bool = False,
    #     run_only: bool = False,
    #     allow_rebuild: bool = True,
    #     allow_rerun: bool = True,
    #     help_msg: str = None,
    # ):

    #     """
    #     Parameters
    #     ----------
    #     name: str
    #         Name of the grading process (ie. 'passoff' or 'coding_standard').  This is just used for folder naming.
    #     lab_name: str
    #         Name of the lab that you are grading (ie. 'lab3').  This is passed back to your run_on_* functions.
    #     work_path: pathlib.Path
    #         Path to directory where student files will be placed.  For example, if you pass in '.', then student code would be placed in './lab3'
    #     grades_csv_path: pathlib.Path
    #         Path to CSV file with student grades exported from LearningSuite.  You need to export netid, first and last name, and any grade columns you want to populate.
    #     grades_col_names: str | list of str
    #         Names of student CSV columns for milestones that will be graded.
    #     points: int | list of int
    #         Number of points the graded milestone(s) are worth.
    #     code_source: CodeSource
    #         Type of source code location, ie. Learning Suite zip file or Github. If Github, then you need to provide the subsequent github_* arguments.  If Learning Suite, then provide the learning_suite_* arguments.
    #     github_csv_path:  Optional[pathlib.Path]
    #         Path to CSV file with Github URL for each student.  There must be a 'Net ID' column name.  One way to get this is to have a Learning Suite quiz where students enter their Github URL, and then export the results.
    #     github_csv_col_name: Optional[str]
    #         Column name in the github_csv_path CSV file that should be used as the Github URL.  Note: This column name may be fixed for every lab, or it could vary, which allows you to handle Github groups, and even students changing groups between labs.
    #     github_tag: Optional[str]
    #         Tag that holds this students submission for this lab.
    #     learning_suite_submissions_zip_path: Optional[pathlib.Path]
    #         Path to zip file with all learning suite submissions.  This zip file should contain one zip file per student (if student has multiple submissions, only the most recent will be used).
    #     learning_suite_groups_csv_path: Optional[pathlib.Path]
    #         If you have groups, this arguments points to a CSV file that contains group names.
    #     learning_suite_groups_csv_col_name: Optional[str]
    #         If you have groups, this arguments provides the column name to use for the group.
    #     run_on_milestone: Callable
    #         This is the main callback function that you should provide to build, run and/or evaluate the student's file.  You can do anything you like in this function (compile and run software, build bitstreams, program boards, etc).

    #         The callback will be called on each graded milestone.  Your callback function will be provided with several arguments (I suggest you make use of \*\*kwargs as I may need to pass more information back in the future):

    #       * lab_name: (str) The lab_name provided earlier.
    #       * milestone_name: (str) Grade CSV column name of milestone to run
    #       * student_code_path (pathlib.Path)  The page to where the student files are stored.
    #       * build: (bool) Whether files should be built/compiled.
    #       * run: (bool) Whether milestone should be run.
    #       * first_names: (list) List of first name of students in the group
    #       * last_names: (list) List of last names of students in the group
    #       * net_ids: (list) List of net_ids of students in the group.
    #       * section: (str) Student section number, assuming 'Section Number' was contained in grades_csv exported from Learning Suite.
    #       * homework_id: (str) Student homework ID, assuming 'Course Homework ID' was contained in grades_csv exported from Learning Suite.
    #       * Return value: (int)
    #         If you return nothing, the default script behavior is that the program will ask the user to input a grade.  If you already know the grade you want to assign, and don't want to prompt the user, just return the grade from this callback.

    #     run_on_lab: Optional[Callable]
    #         This is an additional callback function, but will only be called once, even if you are grading multiple milestones.  It will be called before any milestones are graded.  This is useful for doing one-off actions before running each milestone, or if you are not grading any milestones and only running in analysis mode. This function callback takes the same arguments as the one provided to 'run_on_milestone', except it does not have a 'milestone_name' argument, and you should not return any value.  If you only have single milestone to grade, you can use either callback method, although if you want to return a grade, you will need to use run_on_milestone.

    #     Other Parameters
    #     ----------
    #     format_code: Optional[bool]
    #         Whether you want the student code formatted using clang-format
    #     build_only: Optional[bool]
    #         Whether you only want to build and not run/grade the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.
    #     run_only: Optional[bool]
    #         Whether you only want to run/grade and not build the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.
    #     allow_rebuild: Optional[bool]
    #         When asking for a grade, the program will normally allow the grader to request a "rebuild and run".  If your grader doesn't support this, then set this to False.
    #     allow_rerun: Optional[bool]
    #         When asking for a grade, the program will normally allow the grader to request a "re-run only (no rebuld)". If your grader doesn't support this, then set this to False.  At least one of 'allow_rebuild' and 'allow_rerun' must be True.
    #     help_msg: Optional[str]
    #         When the script asks the user for a grade, it will print this message first.  This can be a helpful reminder to the TAs of a grading rubric, things they should watch out for, etc. This can be provided as a single string or a list of strings if there is a different message for each milestone.
    #     """

    def run(self):
        """Call this to start (or resume) the grading process"""

        self.validate_config()

        analyze_only = len(self.grades_col_names) == 0

        # Print starting message
        print_color(TermColors.BLUE, "Running", self.name, "grader for lab", self.lab_name)

        # Read in CSV and validate.  Print # students who need a grade
        student_grades_df = grades_csv.parse_and_check(self.grades_csv_path, self.grades_col_names)

        # Filter by students who need a grade
        if not analyze_only:
            grades_needed_df = grades_csv.filter_need_grade(
                student_grades_df, self.grades_col_names
            )
            print_color(
                TermColors.BLUE,
                str(grades_csv.filter_need_grade(grades_needed_df, self.grades_col_names).shape[0]),
                "students need to be graded.",
            )

        # Add column for group name to DataFrame.
        # For github, students are grouped by their Github repo URL.
        # For learning suite, if set_groups() was never called, then  students are placed in groups by Net ID (so every student in their own group)
        grouped_df = self._group_students(student_grades_df)

        # Create working path directory
        self._create_work_path()

        # For learning suite, unzip their submission and add a column that points to it
        if self.code_source == CodeSource.LEARNING_SUITE:
            self._unzip_submissions()
            grouped_df = self._add_submitted_zip_path_column(grouped_df)

        self._run_grading(student_grades_df, grouped_df, analyze_only)

    def _run_grading(self, student_grades_df, grouped_df, analyze_only):
        # Loop through all of the students/groups and perform grading
        for index, row in grouped_df.iterrows():
            first_names = row["First Name"]
            last_names = row["Last Name"]
            net_ids = row["Net ID"]
            concated_names = ", ".join(
                [
                    (first + " " + last + " (" + net_id + ")")
                    for (first, last, net_id) in zip(first_names, last_names, net_ids)
                ]
            )
            num_group_members = len(net_ids)

            # Check if student/group needs grading
            if not analyze_only:
                num_group_members_need_grade_per_milestone = (
                    grades_csv.num_grades_needed_per_milestone(row, self.grades_col_names)
                )

                if sum(num_group_members_need_grade_per_milestone) == 0:
                    # This student/group is already fully graded
                    continue
            else:
                num_group_members_need_grade_per_milestone = None

            # Print name(s) of who we are grading
            student_work_path = self.work_path / utils.names_to_dir(
                first_names, last_names, net_ids
            )
            student_work_path.mkdir(exist_ok=True)
            print_color(
                TermColors.PURPLE,
                "Analyzing: " if analyze_only else "Grading: ",
                concated_names,
                "-",
                student_work_path.relative_to(self.work_path.parent),
            )

            # Get student code from zip or github.  If this fails it returns False.
            # Code from zip will return modified time (epoch, float). Code from github will return True.
            timestamp = self._get_student_code(index, row, student_work_path)
            if timestamp is False:
                continue
            modified_time = None
            if isinstance(timestamp, float):
                modified_time = datetime.datetime.fromtimestamp(timestamp)
            # Format student code
            if self.format_code:
                print_color(TermColors.BLUE, "Formatting code")
                utils.clang_format_code(student_work_path)

            # variable to flag if build needs to be performed
            # initialize to False as the code must be built at least once
            # (will be false if TA chooses to just re-run and not re-build)
            build = True

            callback_args = {}
            callback_args["lab_name"] = self.lab_name
            callback_args["student_code_path"] = student_work_path
            callback_args["run"] = not self.build_only
            callback_args["first_names"] = first_names
            callback_args["last_names"] = last_names
            callback_args["net_ids"] = net_ids
            if modified_time is not None:
                callback_args["modified_time"] = modified_time
            if "Section Number" in row:
                callback_args["section"] = row["Section Number"]
            if "Course Homework ID" in row:
                callback_args["homework_id"] = row["Course Homework ID"]

            if self.run_on_lab is not None:
                try:
                    self.run_on_lab(
                        **callback_args,
                        build=build and not self.run_only,
                    )
                except CallbackFailed as e:
                    print_color(TermColors.RED, repr(e))
                    continue
                except KeyboardInterrupt:
                    pass

            for col_idx, grade_col_name in enumerate(self.grades_col_names):
                if not analyze_only:
                    if not num_group_members_need_grade_per_milestone[col_idx]:
                        print_color(
                            TermColors.BLUE,
                            "Grade already exists for ",
                            grade_col_name,
                            "(skipping)",
                        )
                        continue

                while True:
                    score = None

                    # Build it and run
                    if self.run_on_milestone is not None:
                        try:
                            score = self.run_on_milestone(
                                **callback_args,
                                milestone_name=grade_col_name,
                                build=build and not self.run_only,
                            )
                        except CallbackFailed as e:
                            print_color(TermColors.RED, repr(e))
                            break
                        except KeyboardInterrupt:
                            print("")

                    # reset the flag
                    build = True

                    if self.build_only:
                        break

                    # Enter score
                    if num_group_members_need_grade_per_milestone[col_idx] < num_group_members:
                        print_color(
                            TermColors.YELLOW,
                            "Warning:",
                            num_group_members - num_group_members_need_grade_per_milestone[col_idx],
                            "group member(s) already have a grade for",
                            grade_col_name,
                            "; this grade will be overwritten.",
                        )

                    if score is None:
                        try:
                            score = self._get_score(
                                concated_names,
                                self.lab_name + "-" + grade_col_name,
                                self.points[col_idx],
                                self.allow_rebuild,
                                self.allow_rerun,
                                self.help_msg[col_idx],
                            )
                        except KeyboardInterrupt:
                            print_color(TermColors.RED, "\nExiting")
                            sys.exit(0)

                    if score == "s":
                        break
                    elif score == "b":
                        continue
                    elif score == "r":
                        # run again, but don't build
                        build = False
                        continue

                    else:
                        # Record score
                        for net_id in net_ids:
                            student_grades_df.at[
                                grades_csv.find_idx_for_netid(student_grades_df, net_id),
                                grade_col_name,
                            ] = score

                        student_grades_df.to_csv(
                            str(self.grades_csv_path),
                            index=False,
                            quoting=csv.QUOTE_ALL,
                        )
                        break

    def _unzip_submissions(self):
        with zipfile.ZipFile(self.learning_suite_submissions_zip_path, "r") as zf:
            for zi in zf.infolist():
                # Remove old zip file if it exists
                unpack_path = self.work_path / zi.filename
                if unpack_path.is_file():
                    unpack_path.unlink()

                # Unzip
                zf.extract(zi, self.work_path)

                # Fix timestamp
                date_time = time.mktime(zi.date_time + (0, 0, -1))
                os.utime(unpack_path, (date_time, date_time))

    def _add_submitted_zip_path_column(self, df):
        # Map dataframe index to student zip file
        df_idx_to_zip_path = {}

        for index, row in df.iterrows():
            # group_name = row["group_id"]
            net_ids = row["Net ID"]

            # Find all submissions that belong to the group
            zip_matches = []
            for net_id in net_ids:
                zip_matches.extend(list(self.work_path.glob("*_" + net_id + "_*.zip")))
            if len(zip_matches) == 0:
                # print("No zip files match", group_name)
                continue
            elif len(zip_matches) > 1:
                # Multiple submissions -- get the latest one
                zip_matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            df_idx_to_zip_path[index] = zip_matches[0]

        df["submitted_zip_path"] = pandas.Series(df_idx_to_zip_path)
        return df

    def _group_students(self, df):
        if self.code_source == CodeSource.GITHUB:
            # For Github source, group name is simply github URL
            df = grades_csv.match_to_github_url(df, self.github_csv_path, self.github_csv_col_name)

            df_needs_grades = grades_csv.filter_need_grade(df, self.grades_col_names)

            print_color(
                TermColors.BLUE,
                str(df_needs_grades.shape[0]),
                "of these students have a github URL.",
            )
            groupby_column = "github_url"

        elif self.groups_csv_path is None:
            # No groups, so just group by netid

            groupby_column = "group_id"
            df = df.copy()
            df[groupby_column] = df["Net ID"]
        else:
            # Add group column from given CSV
            groupby_column = "group_id"
            df = grades_csv.add_group_column_from_csv(
                df, groupby_column, self.groups_csv_path, self.groups_csv_col_name
            )

            # Check how many students remain
            df_needs_grades = grades_csv.filter_need_grade(df, self.grades_col_names)
            print_color(
                TermColors.BLUE,
                str(df_needs_grades.shape[0]),
                "of these students belong to a group.",
            )

        # Group students into their groups
        return df.groupby(groupby_column).agg(lambda x: list(x)).reset_index()

    def _get_student_code(self, index, row, student_work_path):
        if self.code_source == CodeSource.GITHUB:
            # Clone student repo
            print("Student repo url: " + row["github_url"])
            if not student_repos.clone_repo(row["github_url"], self.github_tag, student_work_path):
                return False
            return True

        else:
            zip_path = row["submitted_zip_path"]

            # Skip if student has no submission
            if self.code_source == CodeSource.LEARNING_SUITE and zip_path is None:
                print_color(TermColors.YELLOW, "No submission")
                return False

            # Unzip student files (if student_dir doesn't already exist) and delete zip
            try:
                # Unzip if student work path is empty
                if not list(student_work_path.iterdir()):
                    print(
                        "Unzipping",
                        zip_path,
                        "into",
                        student_work_path.relative_to(self.work_path.parent),
                    )
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(student_work_path)
            except zipfile.BadZipFile:
                print_color(TermColors.RED, "Bad zip file", zip_path)
                return False
            return zip_path.stat().st_mtime

    def _get_score(
        self,
        names,
        assignment_name,
        max_score,
        allow_rebuild,
        allow_rerun,
        extra_message="",
    ):
        if extra_message:
            print_color(TermColors.BOLD, extra_message)
        input_txt = (
            TermColors.BLUE
            + "Enter score for "
            + names
            + ", "
            + (assignment_name + ":")
            + (" (0-" + str(max_score) + "), ")
        )

        input_txt += "'s' to skip, "
        allowed_entrys = ["s"]

        if allow_rebuild:
            input_txt += "'b' to build and run again, "
            allowed_entrys.append("b")
        if allow_rerun:
            input_txt += "'r' to re-run (w/o rebuild), "
            allowed_entrys.append("r")

        # Remmove trailing ", " and terminate
        input_txt = input_txt[:-2] + ":" + TermColors.END

        while True:
            txt = input(input_txt)
            if txt in allowed_entrys:
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

    def _create_work_path(self):
        if self.code_source == CodeSource.LEARNING_SUITE:
            if self.work_path.is_dir() and (
                self.learning_suite_submissions_zip_path.stat().st_mtime
                > self.work_path.stat().st_mtime
            ):
                shutil.rmtree(self.work_path)

        if not self.work_path.is_dir():
            print_color(TermColors.BLUE, "Creating", self.work_path)
            self.work_path.mkdir(exist_ok=True, parents=True)
