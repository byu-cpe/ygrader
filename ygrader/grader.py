""" Main ygrader module"""
import json
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


class GradeItem:
    """Class to track each item that needs to be graded (ie, each item for which a grading callback
    function will be invoked.  This may be used to grade one or more columns from the CSV file."""

    def __init__(self, grader, csv_col_names, fcn, max_points, feedback_col_name, help_msg) -> None:
        self.grader = grader
        self.csv_col_names = csv_col_names
        self.fcn = fcn
        self.max_points = max_points
        self.feedback_col_name = feedback_col_name
        self.help_msg = help_msg

        # Feedback comments
        self.feedback_list_path = self.grader.work_path / (str(csv_col_names) + ".json")
        self.feedback_list = []
        if self.feedback_list_path.is_file():
            with open(self.feedback_list_path, encoding="utf-8") as f:
                self.feedback_list = json.load(f)


class Grader:
    """Grader class"""

    def __init__(
        self,
        lab_name: str,
        grades_csv_path: pathlib.Path,
        work_path: pathlib.Path = pathlib.Path.cwd() / "temp",
    ):
        """
        Parameters
        ----------
        lab_name: str
            Name of the lab/assignment that you are grading (ie. 'lab3').
            This is used for folder naming, logging mesasge, etc., and passed back to your callback functions.
        grades_csv_path: pathlib.Path
            Path to CSV file with student grades exported from LearningSuite.  You need to export netid, first
            and last name, and any grade columns you want to populate.
        work_path: pathlib.Path
            Path to directory where student files will be placed.  For example, if you pass in '.', then student
            code would be placed in './lab3'.  By default the working path is a "temp" folder created in your working directory.
        """
        self.lab_name = lab_name
        self.grades_csv_path = pathlib.Path(grades_csv_path).resolve()

        # Make sure grades csv exists, and that file is writable
        if not self.grades_csv_path.is_file():
            error("grades_csv_path", "(" + str(grades_csv_path) + ")", "does not exist")
        try:
            with open(grades_csv_path, "a", encoding="utf-8"):
                pass
        except PermissionError:
            error(
                "You do not have permissions to modify the grades_csv_path file",
                "(" + str(grades_csv_path) + ").",
                "Is this file open and locked?",
            )

        # Create a working directory
        self.work_path = pathlib.Path(work_path)
        self.work_path = self.work_path / lab_name

        # Read CSV and make sure it isn't empty
        try:
            pandas.read_csv(self.grades_csv_path)
        except pandas.errors.EmptyDataError:
            error("Your grades csv", "(" + str(grades_csv_path) + ")", "appears to be empty")

        # Initialize other class members
        self.items = []
        self.code_source = None
        self.prep_fcn = None
        self.learning_suite_submissions_zip_path = None
        self.github_csv_path = None
        self.github_csv_col_name = None
        self.github_tag = None
        self.github_https = None
        self.groups_csv_path = None
        self.groups_csv_col_name = None
        self.set_other_options()

    def add_item_to_grade(
        self, csv_col_names, grading_fcn, max_points=None, feedback_col_name=None, help_msg=None
    ):
        """Add a new item you want to grade.

        Parameters
        ----------
        csv_col_names: (str | list of str)
            The column name(s) from your grading CSV file that you want to grade.
        grading_fcn: Callable
            The callback function that will perform all your grading work.

            Your callback function will be provided with the following arguments:
                * lab_name (*str*): This will pass back the lab name you passed to *__init__*.
                Useful if you use the same callback function to grade multiple different assignments.
                * student_code_path (*pathlib.Path*): The location where the unzipped/cloned student files are stored.
                * cols_to_grade (*str*): The current CSV column being graded. Typically only needed if you are grading
                multiple different items.
                * points (*int*): The maximum number of points possible for the item being graded, used for validating the
                grade when prompting the user to input a grade.  If your callback function automatically calcuates and
                returns a grade, this argument is ignored.
                * first_names: (*list(str)*) First name(s) of students in the group
                * last_names: (*list(str)*) Last name(s) of students in the group
                * net_ids: (*list(str)*) Net ID(s) of students in the group.
                * build: (*bool*) Whether files should be built/compiled.
                * run: (*bool*) Whether milestone should be run.

            In addition, if your grades CSV exported from Learning Suite has the following information, it will also be
            provided to your callback function:
                * section: (*str*) Student section number, assuming 'Section Number' was contained in grades_csv exported
                from Learning Suite.
                * homework_id: (*str*) Student homework ID, assuming 'Course Homework ID' was contained in grades_csv
                exported from Learning Suite.

            Your callback should return *None* an *int*/*float* (or a list of *int*/*float* if you are grading multiple
            columns in this item).  If you return *None*, then the user will be prompted input a grade.  If you already
            know the grade you want to assign, and don't want to prompt the user, return the grade value(s).

            If there's a problem with the student's submission and you want to skip them, then `raise CallbackFailed`.
            You can provide an argument to this exception with any error message you want printed.

            Since your callback functions will be provided with many arguments, it's best to use keyword arguments:

            .. highlight:: python
            .. code-block:: python

                def my_callback(**kw):
                    lab_name = kw["lab_name"]
                    first_name = kw["first_names"][0]
        max_points: int | list of int
            (Optional) Number of max points for the graded column(s).
        feedback_col_name: str
            (Optional) Name of CSV column that will be used to store comments for student feedback.
        help_msg: str | list of str
            (Optional) When the script asks the user for a grade, it will print this message first.  This can be a helpful
            reminder to the TAs of a grading rubric, things they should watch out for, etc.  If you are grading multiple
            CSV columns, then you should provide a separate help message per column.
        """
        # Check data types
        if not isinstance(grading_fcn, Callable):
            error("'grading_fcn' must be a callable function")

        # Make these into lists, even if there is only one item
        csv_col_names = utils.ensure_tuple(csv_col_names)
        if max_points:
            max_points = utils.ensure_tuple(max_points)

            # Check that # of CSV columns to grade matches # of points list
            if len(csv_col_names) != len(max_points):
                error(
                    "'csv_col_names'",
                    csv_col_names,
                    "has list length =",
                    len(csv_col_names),
                    "but 'max_points'",
                    max_points,
                    "has list length =",
                    str(len(max_points)) + ".",
                    "They must be equal.",
                )

        if help_msg:
            help_msg = utils.ensure_tuple(help_msg)

            # Check that # of CSV columns to grade matches # of help_msg list
            if len(csv_col_names) != len(help_msg):
                error(
                    "'csv_col_names'",
                    csv_col_names,
                    "has list length =",
                    len(csv_col_names),
                    "but 'help_msg'",
                    help_msg,
                    "has list length =",
                    str(len(help_msg)) + ".",
                    "They must be equal.",
                )

        df = pandas.read_csv(self.grades_csv_path)
        for col_name in csv_col_names:
            if col_name not in df:
                error(
                    "Provided grade column name",
                    "(" + col_name + ")",
                    "does not exist in grades_csv_path",
                    "(" + str(self.grades_csv_path) + ").",
                    "Columns:",
                    list(df.columns),
                )
        if feedback_col_name and feedback_col_name not in df:
            error(
                "Provided feedback_col_name",
                "(" + feedback_col_name + ")",
                "does not exist in grades_csv_path",
                "(" + str(self.grades_csv_path) + ").",
                "Columns:",
                list(df.columns),
            )

        item = GradeItem(self, csv_col_names, grading_fcn, max_points, feedback_col_name, help_msg)
        _verify_callback_fcn(grading_fcn, item)
        self.items.append(item)

    def set_submission_system_learning_suite(self, zip_path):
        """
        Call this function if you are using student submissions from Learning Suite.

        Parameters
        ----------
        zip_path: pathlib.Path | str
            Path to the zip file that was downloaded from Learning Suite using *Batch Download*.
        """
        zip_path = pathlib.Path(zip_path)

        self.code_source = CodeSource.LEARNING_SUITE
        self.learning_suite_submissions_zip_path = zip_path

        if not zip_path.is_file():
            error("Provided zip_path", zip_path, "does not exist")

    def set_submission_system_github(
        self, tag, github_url_csv_path, repo_col_name="github_url", use_https=False
    ):
        """
        Call this function if you are using student submissions on Github.

        Parameters
        ----------
        tag: str
            The tag on the students github repository that is used for the submission.
        github_url_csv_path: pathlib.Path | str
            The path to a CSV file containing student Github repository URLs.  This CSV file must have a
            column called 'Net ID'. The repos can be listed as an http:// address or in SSH format (git@).
            They will be coverted as needed depending on the *use_https* argument.
        repo_col_name: str
            The column name in the CSV file that contains the Github URLs.
        use_https: bool
            By default SSH will be used to clone the student repos.  If you want to use an access token or stored
            credentials over https, set this to True.
        """
        self.code_source = CodeSource.GITHUB
        self.github_csv_path = github_url_csv_path
        self.github_csv_col_name = repo_col_name
        self.github_tag = tag
        self.github_https = use_https

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
        """
        This function is used to provide treams to the grader when grading a team-based assignment from
        Learning Suite.  (If grading from Github, the Github URL will be used to determine teams)

        Parameters
        ----------
        csv_path: str
            The path to a CSV file containing group names. This CSV file must have a column called 'Net ID'.
        col_name: str
            The column name in the CSV file that indicates the group name.
        """
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
        allow_rebuild=False,
        allow_rerun=True,
        prep_fcn=None,
    ):
        """
        This can be used to set other options for the grader.

        Parameters
        ----------
        format_code: bool
            Whether you want the student code automatically formatted using clang-format
        build_only: bool
            Whether you only want to build and not run/grade the students code.  This will be passed to your
            callback function, and is useful for labs that take a while to build.  You can build all the code in
            one pass, then return and grade the code later.
        run_only: bool
            Whether you only want to run/grade and not build the students code.  This will be passed to your
            callback function, and is useful for labs that take a while to build.  You can build all the code
            in one pass, then return and grade the code later.
        allow_rebuild: bool
            By default, the program will pass build=True and run=True to your callback on the first invocation,
            and then allow the grader the option to "re-run" the student's code, where build=False and run=True
            would be provided.  If you want to allow the grader to
            specifically request a rebuild, set this to True (default False).
        allow_rerun: bool
            By default, the program will pass build=True and run=True to your callback on the first invocation,
            and then allow the grader the option to "re-run" the student's code, where build=False and run=True
            would be provided.  If your grader can't rerun without rebuilding, then set this to False (default True).
        prep_fcn: Callable
            If you are grading multiple items, then you can use this optional callback to do any one-time prep work.
            This callback is provided the same arguments as the grading callback function, except for *cols_to_grade*
            and *max_points*.  You should not return any value from this callback, but you can `raise CallbackFailed` to skip the student.
        """
        self.format_code = format_code
        self.build_only = build_only
        self.run_only = run_only
        self.allow_rebuild = allow_rebuild
        self.allow_rerun = allow_rerun
        if prep_fcn and not isinstance(prep_fcn, Callable):
            error("The 'prep_fcn' argument must provide a callable function pointer")
        self.prep_fcn = prep_fcn
        if prep_fcn:
            _verify_callback_fcn(prep_fcn, item=None)

        if not (self.allow_rebuild or self.allow_rerun):
            error("At least one of allow_rebuild and allow_rerun needs to be True.")

    def validate_config(self):
        """Check that everything has been configured before running"""
        # Check that callback function has been set up
        if not self.items:
            error(
                "Before calling run(), you must call add_item_to_grade() to add an item to grade."
            )

        # Check that submission source is set
        if self.code_source is None:
            error(
                "Before calling run(), you must set a submission source by either calling "
                + "set_submission_system_learning_suite() or set_submission_system_github()."
            )

    def get_all_csv_cols_to_grade(self):
        """Collelct all columns that will be graded into a single list"""
        return [col for item in self.items for col in item.csv_col_names]

    def run(self):
        """Call this to start (or resume) the grading process"""

        self.validate_config()

        # Print starting message
        print_color(TermColors.BLUE, "Running grader for", self.lab_name)

        # Read in CSV and validate.  Print # students who need a grade
        student_grades_df = grades_csv.parse_and_check(
            self.grades_csv_path, self.get_all_csv_cols_to_grade()
        )

        # Convert columnsdg
        for item in self.items:
            if item.feedback_col_name:
                student_grades_df[item.feedback_col_name] = student_grades_df[
                    item.feedback_col_name
                ].fillna("")

        # Filter by students who need a grade
        grades_needed_df = grades_csv.filter_need_grade(
            student_grades_df, self.get_all_csv_cols_to_grade()
        )
        print_color(
            TermColors.BLUE,
            str(
                grades_csv.filter_need_grade(
                    grades_needed_df, self.get_all_csv_cols_to_grade()
                ).shape[0]
            ),
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

        self._run_grading(student_grades_df, grouped_df)

    def _run_grading(self, student_grades_df, grouped_df):
        # Loop through all of the students/groups and perform grading
        for _, row in grouped_df.iterrows():
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
            num_group_members_need_grade_per_item = grades_csv.num_grades_needed_per_item(
                row, self.items
            )
            if sum(sum(s) for s in num_group_members_need_grade_per_item.values()) == 0:
                # This student/group is already fully graded
                continue

            # Print name(s) of who we are grading
            student_work_path = self.work_path / utils.names_to_dir(
                first_names, last_names, net_ids
            )
            student_work_path.mkdir(exist_ok=True)
            print_color(
                TermColors.PURPLE,
                "\nGrading: ",
                concated_names,
                "-",
                student_work_path.relative_to(self.work_path.parent),
            )

            # Get student code from zip or github.  If this fails it returns False.
            # Code from zip will return modified time (epoch, float). Code from github will return True.
            timestamp = self._get_student_code(row, student_work_path)
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
            # initialize to True as the code must be built at least once
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

            if self.prep_fcn is not None:
                try:
                    self.prep_fcn(
                        **callback_args,
                        build=build and not self.run_only,
                    )
                except CallbackFailed as e:
                    print_color(TermColors.RED, repr(e))
                    continue
                except KeyboardInterrupt:
                    pass

            # Loop through all items that are to be graded
            for item in self.items:
                if sum(num_group_members_need_grade_per_item[item]):
                    print_color(
                        TermColors.BLUE,
                        "Running callback function",
                        "(" + str(item.fcn.__name__) + ")",
                        "to grade",
                        str(item.csv_col_names) + ":",
                    )
                else:
                    # No one in the group needs grades for this
                    print_color(
                        TermColors.BLUE,
                        "Grade already exists for ",
                        item.csv_col_names,
                        "(skipping)",
                    )
                    continue

                while True:
                    scores = None

                    # Build it and run
                    try:
                        scores = item.fcn(
                            **callback_args,
                            csv_col_names=item.csv_col_names,
                            points=item.max_points,
                            build=build and not self.run_only,
                        )
                    except CallbackFailed as e:
                        print_color(TermColors.RED, repr(e))
                        break
                    except KeyboardInterrupt:
                        print("")

                    # reset the flag
                    build = True

                    # If we are only buildiing the code in preparation of grading later, then exit now before asking for a grade
                    if self.build_only:
                        break

                    for i, col in enumerate(item.csv_col_names):
                        if num_group_members_need_grade_per_item[item][i] < num_group_members:
                            print_color(
                                TermColors.YELLOW,
                                "Warning:",
                                num_group_members - num_group_members_need_grade_per_item[item][i],
                                "group member(s) already have a grade for",
                                col,
                                "; this grade will be overwritten.",
                            )

                    if scores is None:
                        # If no score was returned by the callback function, prompt the user for a score.
                        try:
                            scores, feedback = self._get_scores(concated_names, item)
                        except KeyboardInterrupt:
                            print_color(TermColors.RED, "\nExiting")
                            sys.exit(0)
                    else:
                        # If score(s) were returned, make sure the length matches the number of columns to be graded
                        scores = utils.ensure_tuple(scores)
                        if len(item.csv_col_names) != len(scores):
                            error(
                                "The callback should be grading",
                                len(item.csv_col_names),
                                "column(s)",
                                "(" + str(item.csv_col_names) + "),",
                                "but",
                                len(scores),
                                "values were returned.",
                            )

                    if scores == "s":
                        break
                    if scores == "b":
                        continue
                    if scores == "r":
                        # run again, but don't build
                        build = False
                        continue

                    # Record score
                    for net_id in net_ids:
                        row_idx = grades_csv.find_idx_for_netid(student_grades_df, net_id)

                        for (i, col) in enumerate(item.csv_col_names):
                            student_grades_df.at[row_idx, col] = scores[i]

                        if item.feedback_col_name:
                            existing_feedback = student_grades_df.at[
                                row_idx, item.feedback_col_name
                            ].strip()
                            if existing_feedback and (existing_feedback[-1] != "."):
                                existing_feedback += ". "

                            # Append new feedback
                            student_grades_df.at[row_idx, item.feedback_col_name] = (
                                existing_feedback + feedback
                            )

                    student_grades_df.to_csv(
                        str(self.grades_csv_path),
                        index=False,
                        quoting=csv.QUOTE_ALL,
                    )
                    break

    def _unzip_submissions(self):
        with zipfile.ZipFile(self.learning_suite_submissions_zip_path, "r") as f:
            for zip_info in f.infolist():
                # Remove old zip file if it exists
                unpack_path = self.work_path / zip_info.filename
                if unpack_path.is_file():
                    unpack_path.unlink()

                # Unzip
                f.extract(zip_info, self.work_path)

                # Fix timestamp
                date_time = time.mktime(zip_info.date_time + (0, 0, -1))
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
            if len(zip_matches) > 1:
                # Multiple submissions -- get the latest one
                zip_matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            df_idx_to_zip_path[index] = zip_matches[0]

        df["submitted_zip_path"] = pandas.Series(df_idx_to_zip_path)
        df["submitted_zip_path"] = df["submitted_zip_path"].fillna(value="")
        return df

    def _group_students(self, df):
        if self.code_source == CodeSource.GITHUB:
            # For Github source, group name is simply github URL
            df = grades_csv.match_to_github_url(
                df, self.github_csv_path, self.github_csv_col_name, self.github_https
            )

            df_needs_grades = grades_csv.filter_need_grade(df, self.get_all_csv_cols_to_grade())

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
            df_needs_grades = grades_csv.filter_need_grade(df, self.get_all_csv_cols_to_grade())
            print_color(
                TermColors.BLUE,
                str(df_needs_grades.shape[0]),
                "of these students belong to a group.",
            )

        # Group students into their groups
        return df.groupby(groupby_column).agg(list).reset_index()

    def _get_student_code(self, row, student_work_path):
        if self.code_source == CodeSource.GITHUB:
            # Clone student repo
            print("Student repo url: " + row["github_url"])
            if not student_repos.clone_repo(row["github_url"], self.github_tag, student_work_path):
                return False
            return True

        # Otherwise, this is a learning suite submission
        zip_path = row["submitted_zip_path"]

        # Skip if student has no submission
        if self.code_source == CodeSource.LEARNING_SUITE and zip_path == "":
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
                with zipfile.ZipFile(zip_path, "r") as f:
                    f.extractall(student_work_path)
        except zipfile.BadZipFile:
            print_color(TermColors.RED, "Bad zip file", zip_path)
            return False
        return zip_path.stat().st_mtime

    def _get_scores(self, names, item):
        """Prompts the user for a score for the grade column(s) for the given item."""
        fpad = " " * 8
        fpad2 = " " * 4
        pad = 10
        feedback = ""
        scores = []

        for (i, grade_col) in enumerate(item.csv_col_names):
            points = item.max_points[i] if item.max_points else None
            while True:
                print("")
                if item.help_msg:
                    print_color(TermColors.BOLD, item.help_msg[i])

                ################### Build input menu #######################
                input_txt = (
                    TermColors.BLUE
                    + "Enter a grade for "
                    + names
                    + ", "
                    + (TermColors.UNDERLINE + grade_col + TermColors.END + TermColors.BLUE)
                    + ":\n"
                )

                # Add current feedback
                if item.feedback_col_name:
                    input_txt += (
                        fpad
                        + "Pending feedback: "
                        + TermColors.END
                        + feedback
                        + TermColors.BLUE
                        + "\n"
                    )

                # Add score input
                input_txt += (
                    fpad2
                    + (("0-" + str(points)) if points else "#").ljust(pad)
                    + "Enter a score to finish and save\n"
                )

                # Enter feedback
                allowed_feedback = {}
                if item.feedback_col_name:
                    input_txt += (
                        fpad2
                        + "str".ljust(pad)
                        + "Enter a string with any new feedback, or select from prevous feedback:\n"
                    )
                    for idx, f in enumerate(item.feedback_list):
                        input_txt += fpad2 + ("f" + str(idx)).ljust(pad + 2) + f + "\n"
                        allowed_feedback["f" + str(idx)] = f

                    input_txt += fpad2 + "'c'".ljust(pad) + "Clear entered feedback\n"
                    allowed_feedback["c"] = ""

                input_txt += fpad2 + "'s'".ljust(pad) + "Skip to next student\n"
                allowed_cmds = ["s"]

                if self.allow_rebuild:
                    input_txt += fpad2 + "'b'".ljust(pad) + "Build and run again\n"
                    allowed_cmds.append("b")
                if self.allow_rerun:
                    input_txt += fpad2 + "'r'".ljust(pad) + "Re-run"
                    if self.allow_rebuild:
                        input_txt += " (w/o rebuild)"
                    input_txt += "\n"
                    allowed_cmds.append("r")

                # Remmove trailing ", " and terminate
                input_txt += ">>> " + TermColors.END

                ################### Get and handle user input #######################
                txt = input(input_txt)

                # Check for commands
                if txt in allowed_cmds:
                    scores = txt
                    break

                # Check for integer input
                try:
                    score = float(txt)
                    if (points is None) or (0 <= score <= points):
                        scores.append(score)
                        break
                    print("Invalid input. Try again.")
                except ValueError:
                    pass

                # Check for feedback input
                if txt in allowed_feedback:
                    if txt == "c":
                        feedback = ""
                        continue
                    feedback_to_add = allowed_feedback[txt]

                else:
                    txt = txt.capitalize()
                    if txt not in item.feedback_list:
                        item.feedback_list.append(txt)
                        with open(item.feedback_list_path, "w", encoding="utf-8") as f:
                            json.dump(item.feedback_list, f)
                    feedback_to_add = txt

                # Assume input is feedback
                if feedback and feedback[-1] != ".":
                    feedback += ". "
                feedback += feedback_to_add

            # If non-integer returned, then user asked for something like re-run, so stop prompting for grades and exit this function
            if isinstance(scores, str):
                return (scores, "")

        return (scores, feedback)

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


def _verify_callback_fcn(fcn, item):
    callback_args = [
        "lab_name",
        "student_code_path",
        "run",
        "build",
        "first_names",
        "last_names",
        "net_ids",
    ]
    if item:
        if item.max_points:
            callback_args.append("max_points")

        # If this is a fcn for a graded item (not a prep-only function), then
        # this argument is required.
        callback_args.append("csv_col_names")

    callback_args_optional = [
        "modified_time",
        "section",
        "homework_id",
    ]

    # Check that callback function(s) are valid
    argspec = inspect.getfullargspec(fcn)

    # Check that kwargs is enabled
    if argspec.varkw is None:
        error(
            "Your callback function",
            "(" + fcn.__name__ + ")",
            "should accept keyward arguments (**kw). This is needed because the grader may provide "
            + "different optional arguments to your callback depending on what data it has available",
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
                "(" + fcn.__name__ + ")",
                "takes a named argument",
                "'" + named_arg + "'",
                "but this is not provided by the grader. Please remove this argument or the grader "
                + "will not be able to call your callback function correctly. Available callback arguments:",
                str(callback_args),
            )
        elif named_arg not in callback_args:
            warning(
                "Your callback function",
                "(" + fcn.__name__ + ")",
                "takes a named argument",
                "'" + named_arg + "'",
                "but this argument is not always provided by the grader.",
                "If it is missing from your grades CSV file this will cause a runtime error.",
                "Please consider use keyword arguments (**kw) instead.",
            )
