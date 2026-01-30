"""Main ygrader module"""

# pylint: disable=too-many-lines

import enum
import inspect
import os
import pathlib
import re
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import pandas

from . import grades_csv, student_repos, utils
from .grading_item import GradeItem
from .score_input import display_completion_menu
from .utils import (
    CallbackFailed,
    TermColors,
    directory_is_empty,
    error,
    print_color,
    warning,
)


class CodeSource(enum.Enum):
    """Used to indicate whether the student code is submitted via LearningSuite or Github"""

    LEARNING_SUITE = 1
    GITHUB = 2


class Grader:
    """Grader class"""

    def __init__(
        self,
        lab_name: str,
        class_list_csv_path: pathlib.Path,
        work_path: pathlib.Path = pathlib.Path.cwd() / "temp",
    ):
        """
        Parameters
        ----------
        lab_name: str
            Name of the lab/assignment that you are grading (ie. 'lab3').
            This is used for logging messages and passed back to your callback functions.
        class_list_csv_path: pathlib.Path
            Path to CSV file with class list exported from LearningSuite. You need to export netid, first
            and last name columns.
        work_path: pathlib.Path
            Path to directory where student files will be placed.  For example, if you pass in '.', then student
            code would be placed in './lab3'.  By default the working path is a "temp" folder created in your working directory.
        """
        self.lab_name = lab_name
        self.class_list_csv_path = pathlib.Path(class_list_csv_path).resolve()

        # Make sure class list csv exists and is readable
        if not self.class_list_csv_path.is_file():
            error(
                "class_list_csv_path",
                "(" + str(class_list_csv_path) + ")",
                "does not exist",
            )
        try:
            with open(class_list_csv_path, "r", encoding="utf-8"):
                pass
        except PermissionError:
            error(
                "You do not have permissions to read the class_list_csv_path file",
                "(" + str(class_list_csv_path) + ").",
                "Is this file open and locked?",
            )

        # Create a working directory
        self.work_path = pathlib.Path(work_path).resolve()
        self.work_path.mkdir(parents=True, exist_ok=True)

        # Read CSV and make sure it isn't empty
        try:
            pandas.read_csv(self.class_list_csv_path)
        except pandas.errors.EmptyDataError:
            error(
                "Your class list csv",
                "(" + str(class_list_csv_path) + ")",
                "appears to be empty",
            )

        # Initialize other class members
        self.items = []
        self.code_source = None
        self.prep_fcn = None
        self.last_graded_net_ids = None  # Track last fully graded student for undo
        self.show_completion_menu = True  # Show menu when grading completes
        self.learning_suite_submissions_zip_path = None
        self.github_csv_path = None
        self.github_csv_col_name = None
        self.github_tag = None
        self.github_https = None
        self.groups_csv_path = None
        self.groups_csv_col_name = None
        self.set_other_options()

    def add_item_to_grade(
        self,
        item_name,
        grading_fcn,
        deductions_yaml_path,
        *,
        grading_fcn_args_dict=None,
        max_points=None,
    ):
        """Add a new item you want to grade.

        Parameters
        ----------
        grading_fcn: Callable
            The callback function that will perform all your grading work. Your callback function will be provided with the following arguments:

              * lab_name (*str*): This will pass back the lab name you passed to *__init__*.
                Useful if you use the same callback function to grade multiple different assignments.
              * item_name (*str*): The name of the item being graded (e.g., "answers.txt").
              * student_code_path (*pathlib.Path*): The location where the unzipped/cloned student files are stored.
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

            Your callback should return *None* or an *int*/*float*.  If you return *None*, then the user will be prompted to input a grade.  If you already
            know the grade you want to assign, and don't want to prompt the user, return the grade value.
            If feedback is enabled, return a tuple of (score, feedback).

            If there's a problem with the student's submission and you want to skip them, then `raise CallbackFailed`.
            You can provide an argument to this exception with any error message you want printed.

            Since your callback functions will be provided with many arguments, it's best to use keyword arguments:

            .. highlight:: python
            .. code-block:: python

                def my_callback(**kw):
                    lab_name = kw["lab_name"]
                    first_name = kw["first_names"][0]
        deductions_yaml_path: pathlib.Path
            Path to the YAML file for storing deductions and tracking grading status.
        grading_fcn_args_dict: dict
            (Optional) A dictionary of additional arguments that will be passed to your grading function.
        max_points: int
            (Optional) Number of max points for the graded column.
        """
        # Check data types
        if not isinstance(grading_fcn, Callable):
            error("'grading_fcn' must be a callable function")

        item = GradeItem(
            self,
            item_name,
            fcn=grading_fcn,
            max_points=max_points,
            deductions_yaml_path=deductions_yaml_path,
            fcn_args_dict=grading_fcn_args_dict,
        )
        _verify_callback_fcn(
            grading_fcn,
            item,
            fcn_extra_args_dict=grading_fcn_args_dict,
            github_configured=(self.code_source == CodeSource.GITHUB),
        )
        self.items.append(item)

    def add_item_to_grade_from_config(
        self,
        grade_item_config,
        grading_fcn,
    ):
        """Add a new item to grade using a GradeItemConfig object.

        This is a convenience method that extracts all necessary information from
        a GradeItemConfig object and calls add_item_to_grade.

        Parameters
        ----------
        grade_item_config: GradeItemConfig
            The configuration object for the grade item, containing points,
            feedback_path, and other_data.
        grading_fcn: Callable
            The callback function that will perform the grading work.
            See add_item_to_grade for details on the callback function signature.
        """
        self.add_item_to_grade(
            grading_fcn=grading_fcn,
            item_name=grade_item_config.name,
            deductions_yaml_path=grade_item_config.feedback_path,
            grading_fcn_args_dict=grade_item_config.other_data,
            max_points=grade_item_config.points,
        )

    def set_submission_system_learning_suite(self, zip_path):
        """
        Call this function if you are using student submissions from Learning Suite.

        Parameters
        ----------
        zip_path: pathlib.Path | str
            Path to the zip file that was downloaded from Learning Suite using *Batch Download*.
        """
        zip_path = pathlib.Path(zip_path).resolve()

        self.code_source = CodeSource.LEARNING_SUITE
        self.learning_suite_submissions_zip_path = zip_path

        if not zip_path.is_file():
            error("Provided zip_path", zip_path, "does not exist")

    def set_submission_system_github(
        self,
        tag,
        github_url_csv_path,
        repo_col_name="github_url",
        *,
        use_https=False,
        build_from_classroster=None,
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
        build_from_classroster: (str, str)
            If the CSV file does not contain the github URLs, but instead contains a class roster from Git Classroom,
            then this should provide the organization and classroom prefix name to build the github URLs.
        """
        self.code_source = CodeSource.GITHUB
        self.github_csv_path = pathlib.Path(github_url_csv_path).resolve()
        self.github_csv_col_name = repo_col_name
        self.github_tag = tag
        self.github_https = use_https

        if not github_url_csv_path.is_file():
            error(
                "Provided github_url_csv_path",
                "(" + str(github_url_csv_path) + ")",
                "does not exist",
            )
        if build_from_classroster is not None and repo_col_name != "github_url":
            error(
                "When using build_from_classroster, don't override repo_col_name.",
            )

        df = pandas.read_csv(github_url_csv_path)

        # If building from class roster, build github URLs
        if build_from_classroster is not None:
            org, prefix = build_from_classroster
            # Classroom exports call the Net ID column "identifier"; normalize it
            if "identifier" in df.columns and "Net ID" not in df.columns:
                df = df.rename(columns={"identifier": "Net ID"})
            # Build SSH URLs: git@github.com:<org>/<prefix>-<github_username>.git
            df[self.github_csv_col_name] = df.apply(
                lambda row: f"git@github.com:{org}/{prefix}-{row['github_username']}.git",
                axis=1,
            )
            # Write the updated dataframe back to the CSV
            self.github_csv_path = self.work_path / "temp_github_urls.csv"
            df.to_csv(self.github_csv_path, index=False)

        # Make sure repo_col_name exists
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

        self.groups_csv_path = pathlib.Path(csv_path).resolve()
        self.groups_csv_col_name = col_name

        if not csv_path.is_file():
            error("Provided groups csv_path", csv_path, "does not exist")

        df = pandas.read_csv(self.groups_csv_path)
        if col_name not in df:
            error("Provided groups col_name", col_name, "does not exist in", csv_path)

    def set_other_options(
        self,
        *,
        format_code=False,
        build_only=False,
        run_only=False,
        allow_rebuild=False,
        allow_rerun=True,
        prep_fcn=None,
        dry_run_first=False,
        dry_run_all=False,
        workflow_hash=None,
        parallel_workers=None,
        show_completion_menu=True,
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
            in one pass, then return and grade the code later.  When using GitHub submissions, this will skip
            fetching/cloning repositories and assume they already exist in a good state.  If a student's
            repository does not exist, an error will be reported and that student will be skipped.
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
        dry_run_first: bool
            Perform a dry run, calling your callback function to perform grading, but not updating the grades CSV file.
            The callback is only run for the first student.
        dry_run_all: bool
            Perform a dry run, calling your callback function to perform grading, but not updating the grades CSV file.
            The callback is run for each student.
        workflow_hash: str
            (Optional) Expected hash of the GitHub workflow file. If provided, the workflow file will be verified
            before grading each student. If the hash doesn't match, a warning will be displayed indicating
            the student may have modified the workflow system.
        parallel_workers: int or None
            If set to an integer, process students in parallel using that many workers.
            Only works with build_only mode since interactive grading cannot be parallelized.
            Default is None (sequential processing).
        show_completion_menu: bool
            Whether to show the completion menu when all students are graded.
            Default is True.
        """
        self.format_code = format_code
        self.build_only = build_only
        self.run_only = run_only
        self.allow_rebuild = allow_rebuild
        self.allow_rerun = allow_rerun
        self.workflow_hash = workflow_hash
        self.parallel_workers = parallel_workers
        if prep_fcn and not isinstance(prep_fcn, Callable):
            error("The 'prep_fcn' argument must provide a callable function pointer")
        self.prep_fcn = prep_fcn
        if prep_fcn:
            _verify_callback_fcn(
                prep_fcn,
                item=None,
                github_configured=(self.code_source == CodeSource.GITHUB),
            )

        if not (self.allow_rebuild or self.allow_rerun):
            error("At least one of allow_rebuild and allow_rerun needs to be True.")

        if dry_run_first and dry_run_all:
            error("Select only one of 'dry_run_first' and 'dry_run_all'")
        self.dry_run_first = dry_run_first
        self.dry_run_all = dry_run_all

        if parallel_workers is not None and not build_only:
            error("parallel_workers is only supported when build_only=True")

        self.show_completion_menu = show_completion_menu

    def _validate_config(self):
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

    def _get_all_csv_cols_to_grade(self):
        """Collect all columns that will be graded into a single list.

        Returns empty list since grades are stored in deductions files, not CSV columns.
        """
        return []

    def run(self):
        """Call this to start (or resume) the grading process"""

        self._validate_config()

        # Print starting message
        print_color(TermColors.BLUE, "Running grader for", self.lab_name)

        # Read in CSV and validate.
        student_grades_df = grades_csv.parse_and_check(
            self.class_list_csv_path, self._get_all_csv_cols_to_grade()
        )

        # Add column for group name to DataFrame.
        # For github, students are grouped by their Github repo URL.
        # For learning suite, if set_groups() was never called, then  students are placed in groups by Net ID (so every student in their own group)
        grouped_df = self._group_students(student_grades_df)

        # Count students who need grading based on deductions file
        students_need_grading = 0
        for _, row in grouped_df.iterrows():
            net_ids = grades_csv.get_net_ids(row)
            num_need_grade = sum(
                item.num_grades_needed_deductions(net_ids) for item in self.items
            )
            if num_need_grade > 0:
                students_need_grading += 1

        print_color(
            TermColors.BLUE,
            str(students_need_grading),
            "students need to be graded.",
        )

        # Create working path directory
        self._create_work_path()

        # For learning suite, unzip their submission and add a column that points to it
        if self.code_source == CodeSource.LEARNING_SUITE:
            pass
            # self._unzip_submissions()
            # sys.exit(0)
            # grouped_df = self._add_submitted_zip_path_column(grouped_df)

        if self.parallel_workers is not None:
            self._run_grading_parallel(student_grades_df, grouped_df)
        else:
            self._run_grading_sequential(student_grades_df, grouped_df)

    def _run_grading(self, student_grades_df, grouped_df):
        """Alias for backwards compatibility."""
        if self.parallel_workers is not None:
            self._run_grading_parallel(student_grades_df, grouped_df)
        else:
            self._run_grading_sequential(student_grades_df, grouped_df)

    def _run_grading_sequential(self, student_grades_df, grouped_df):
        # Sort by first name for consistent grading order (matches display name sorting in [g] menu)
        # After groupby().agg(list), "First Name" is a list, so we sort by the first element
        sorted_df = grouped_df.sort_values(
            by="First Name", key=lambda x: x.apply(lambda names: names[0].lower())
        )

        # Convert to list for index-based iteration (needed for going back)
        rows_list = list(sorted_df.iterrows())

        # Outer loop to allow re-grading after deleting from completion menu
        while True:
            idx = 0
            prev_idx = None  # Track previous student index for undo

            # Loop through all of the students/groups and perform grading
            while idx < len(rows_list):
                _, row = rows_list[idx]
                first_names = grades_csv.get_first_names(row)
                last_names = grades_csv.get_last_names(row)
                net_ids = grades_csv.get_net_ids(row)
                concated_names = grades_csv.get_concated_names(row)

                # Check if student/group needs grading
                num_group_members_need_grade_per_item = [
                    item.num_grades_needed_deductions(net_ids) for item in self.items
                ]

                if sum(num_group_members_need_grade_per_item) == 0:
                    # This student/group is already fully graded
                    idx += 1
                    continue

                # Print name(s) of who we are grading
                student_work_path = self.work_path / utils.names_to_dir(
                    first_names, last_names, net_ids
                )
                print_color(
                    TermColors.PURPLE,
                    "\nGrading: ",
                    concated_names,
                    "-",
                    student_work_path.relative_to(self.work_path.parent),
                )

                # Get student code from zip or github.  If this fails it returns False.
                # Code from zip will return modified time (epoch, float). Code from github will return True.
                success = self._get_student_code(row, student_work_path)
                if not success:
                    idx += 1
                    continue

                # Format student code
                if self.format_code:
                    print_color(TermColors.BLUE, "Formatting code")
                    utils.clang_format_code(student_work_path)

                callback_args = {}
                callback_args["lab_name"] = self.lab_name
                callback_args["student_code_path"] = student_work_path
                callback_args["run"] = not self.build_only
                callback_args["first_names"] = first_names
                callback_args["last_names"] = last_names
                callback_args["net_ids"] = net_ids
                callback_args["output"] = sys.stdout  # Default to stdout in sequential mode
                if self.code_source == CodeSource.GITHUB:
                    callback_args["repo_url"] = row["github_url"]
                    callback_args["tag"] = self.github_tag
                if "Section Number" in row:
                    callback_args["section"] = row["Section Number"]
                if "Course Homework ID" in row:
                    callback_args["homework_id"] = row["Course Homework ID"]

                if self.prep_fcn is not None:
                    try:
                        self.prep_fcn(
                            **callback_args,
                            build=not self.run_only,
                        )
                    except CallbackFailed as e:
                        print_color(TermColors.RED, repr(e))
                        idx += 1
                        continue
                    except KeyboardInterrupt:
                        pass

                # Loop through all items that are to be graded
                go_back = False
                for item in self.items:
                    go_back = item.run_grading(student_grades_df, row, callback_args)
                    if go_back:
                        break  # Stop grading items for this student if going back

                if go_back and prev_idx is not None:
                    # Go back to previous student
                    idx = prev_idx
                    prev_idx = None  # Clear so we can't go back twice in a row
                    self.last_graded_net_ids = None  # Clear since we're undoing
                    continue

                # Track this student as last graded (only if all items completed normally)
                if (
                    not go_back
                    and not self.build_only
                    and not self.dry_run_first
                    and not self.dry_run_all
                ):
                    self.last_graded_net_ids = tuple(net_ids)

                if self.dry_run_first:
                    print_color(
                        TermColors.YELLOW,
                        "'dry_run_first' is set, so exiting after first student.",
                    )
                    break

                # Move to next student and remember this one for potential undo
                prev_idx = idx
                idx += 1

            # Show completion menu when all students are done (unless disabled or in special modes)
            # If a grade is deleted from the menu, re-run the grading loop
            if (
                not self.show_completion_menu
                or self.build_only
                or self.dry_run_first
                or self.dry_run_all
            ):
                break  # Exit outer loop - no completion menu

            # Get names_by_netid from first item for display purposes
            names_by_netid = self.items[0].names_by_netid if self.items else None
            if display_completion_menu(self.items, names_by_netid):
                # A grade was deleted, continue outer loop to re-run grading
                self.last_graded_net_ids = None
                continue
            # User exited normally
            break

    def _process_single_student_build(self, row):
        """Process a single student for parallel build mode. Returns (net_ids, success, message, log_path)."""
        first_names = grades_csv.get_first_names(row)
        last_names = grades_csv.get_last_names(row)
        net_ids = grades_csv.get_net_ids(row)

        # Check if student/group needs grading
        num_group_members_need_grade_per_item = [
            item.num_grades_needed_deductions(net_ids) for item in self.items
        ]

        if sum(num_group_members_need_grade_per_item) == 0:
            return (net_ids, None, "Already graded", None)  # None indicates skip

        # Create a temp file to capture output early so all messages go to it
        # pylint: disable-next=consider-using-with
        log_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".log", prefix=f"ygrader_{net_ids[0]}_"
        )
        log_path = log_file.name

        student_work_path = self.work_path / utils.names_to_dir(
            first_names, last_names, net_ids
        )

        # Build student info dict to pass to helper
        student_info = {
            "row": row,
            "net_ids": net_ids,
            "first_names": first_names,
            "last_names": last_names,
            "student_work_path": student_work_path,
        }

        # Run the build steps and capture any failure
        success, message = self._run_build_steps(student_info, log_file)

        log_file.close()
        return (net_ids, success, message, log_path)

    def _run_build_steps(  # pylint: disable=too-many-return-statements
        self, student_info, log_file
    ):
        """Run the build steps for a single student. Returns (success, message)."""
        row = student_info["row"]
        student_work_path = student_info["student_work_path"]

        # Get student code
        try:
            success = self._get_student_code(row, student_work_path, output=log_file)
            if not success:
                return (False, "Failed to get student code")
        except Exception as e:  # pylint: disable=broad-exception-caught
            return (False, f"Error getting code: {e}")

        # Format student code
        if self.format_code:
            try:
                utils.clang_format_code(student_work_path)
            except Exception as e:  # pylint: disable=broad-exception-caught
                return (False, f"Error formatting code: {e}")

        callback_args = {}
        callback_args["lab_name"] = self.lab_name
        callback_args["student_code_path"] = student_work_path
        callback_args["run"] = False  # build_only mode
        callback_args["first_names"] = student_info["first_names"]
        callback_args["last_names"] = student_info["last_names"]
        callback_args["net_ids"] = student_info["net_ids"]
        if self.code_source == CodeSource.GITHUB:
            callback_args["repo_url"] = row["github_url"]
            callback_args["tag"] = self.github_tag
        if "Section Number" in row:
            callback_args["section"] = row["Section Number"]
        if "Course Homework ID" in row:
            callback_args["homework_id"] = row["Course Homework ID"]

        if self.prep_fcn is not None:
            try:
                self.prep_fcn(
                    **callback_args,
                    build=True,
                )
            except CallbackFailed as e:
                return (False, f"Prep failed: {e}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                return (False, f"Prep error: {e}")

        # Call the grading callback for each item (with build=True, run=False for build_only mode)
        for item in self.items:
            # Add item-specific args
            item_callback_args = callback_args.copy()
            item_callback_args["item_name"] = item.item_name
            if item.fcn_args_dict:
                item_callback_args.update(item.fcn_args_dict)

            try:
                item.fcn(
                    **item_callback_args,
                    points=item.max_points,
                    build=True,
                    output=log_file,  # Redirect output to temp file
                )
            except CallbackFailed as e:
                return (False, f"Grading callback failed: {e}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                return (False, f"Grading callback error: {e}")

        return (True, "Success")

    def _run_grading_parallel(self, _student_grades_df, grouped_df):
        """Run grading in parallel for build_only mode."""
        # Sort by last name for consistent ordering
        sorted_df = grouped_df.sort_values(
            by="Last Name", key=lambda x: x.apply(lambda names: names[0].lower())
        )

        rows_list = list(sorted_df.iterrows())
        total = len(rows_list)

        print_color(
            TermColors.BLUE,
            f"Running parallel build with {self.parallel_workers} workers for {total} students...\n",
        )

        success_count = 0
        fail_count = 0
        skip_count = 0

        # Use a lock for thread-safe printing
        print_lock = threading.Lock()

        def process_and_report(row):
            nonlocal success_count, fail_count, skip_count
            net_ids, success, message, log_path = self._process_single_student_build(
                row
            )
            net_id_str = (
                ", ".join(net_ids) if isinstance(net_ids, list) else str(net_ids)
            )

            with print_lock:
                if success is None:
                    skip_count += 1
                    # Don't print skipped students
                elif success:
                    success_count += 1
                    if log_path:
                        print_color(
                            TermColors.GREEN,
                            f"[DONE] {net_id_str} - {message} (see {log_path})",
                        )
                    else:
                        print_color(
                            TermColors.GREEN, f"[DONE] {net_id_str} - {message}"
                        )
                else:
                    fail_count += 1
                    if log_path:
                        print_color(
                            TermColors.RED,
                            f"[FAIL] {net_id_str} - {message} (see {log_path})",
                        )
                    else:
                        print_color(TermColors.RED, f"[FAIL] {net_id_str} - {message}")

        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            futures = []
            for i, (_, row) in enumerate(rows_list):
                futures.append(executor.submit(process_and_report, row))
                # Stagger thread starts to avoid overwhelming SSH servers
                if i < self.parallel_workers:
                    time.sleep(0.5)

            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    with print_lock:
                        print_color(TermColors.RED, f"[ERROR] Unexpected error: {e}")

        print_color(
            TermColors.BLUE,
            f"\nCompleted: {success_count} success, {fail_count} failed, {skip_count} skipped",
        )

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
            net_ids = grades_csv.get_net_ids(row)

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

            df_needs_grades = grades_csv.filter_need_grade(
                df, self._get_all_csv_cols_to_grade()
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
            df_needs_grades = grades_csv.filter_need_grade(
                df, self._get_all_csv_cols_to_grade()
            )
            print_color(
                TermColors.BLUE,
                str(df_needs_grades.shape[0]),
                "of these students belong to a group.",
            )

        # Group students into their groups
        return df.groupby(groupby_column).agg(list).reset_index()

    def _get_student_code(self, row, student_work_path, output=None):
        if self.code_source == CodeSource.GITHUB:
            return self._get_student_code_github(row, student_work_path, output=output)

        # else:
        return self._get_student_code_learning_suite(
            row, student_work_path, output=output
        )

    def _get_student_code_github(self, row, student_work_path, output=None):
        if output is None:
            output = sys.stdout

        # If run_only mode, skip fetching and just verify the repo exists
        if self.run_only:
            if student_work_path.is_dir() and list(student_work_path.iterdir()):
                print(
                    f"run_only mode: Using existing repo at {student_work_path}",
                    file=output,
                )
                return True
            msg = f"run_only mode: Repo does not exist at {student_work_path}"
            if output is sys.stdout:
                print_color(TermColors.RED, msg)
            else:
                print(msg, file=output)
            return False

        student_work_path.mkdir(parents=True, exist_ok=True)

        # Clone student repo
        https_url = student_repos.convert_github_url_format(
            row["github_url"], to_https=True
        )
        print("Student repo url: " + https_url, file=output)
        if not student_repos.clone_repo(
            row["github_url"], self.github_tag, student_work_path, output=output
        ):
            return False
        return True

    def _get_student_code_learning_suite(self, row, student_work_path, output=None):
        if output is None:
            output = sys.stdout
        print(
            f"Extracting submitted files for {grades_csv.get_concated_names(row)}...",
            file=output,
        )
        if student_work_path.is_dir() and not directory_is_empty(student_work_path):
            # Code already extracted from Zip, return
            print("  Files already extracted previously.", file=output)
            return True

        student_work_path.mkdir(parents=True, exist_ok=True)

        # Keep track of last file extracted by name
        extracted_by_name = {}

        # Track how many files of each name are extracted so we can warn about duplicate submissions
        count_by_filename = defaultdict(int)

        with zipfile.ZipFile(self.learning_suite_submissions_zip_path, "r") as top_zip:
            # Loop through all files in top-level zip file
            for file in top_zip.infolist():
                if file.is_dir():
                    continue

                # Loop through everyone in the group
                for netid in grades_csv.get_net_ids(row):
                    # Check if file belongs to student
                    match = re.match("^.*?_" + netid + "_(.*)$", file.filename)
                    if not match:
                        match = re.match("^.*? " + netid + "-(.*)$", file.filename)
                    if not match:
                        continue

                    # Handle regular files (not zip files)
                    if not file.filename.lower().endswith(".zip"):
                        extract_to_name = match.group(1)

                        count_by_filename[extract_to_name] += 1

                        # If we've already extracted a file of this name, don't overwrite if older
                        if extract_to_name in extracted_by_name:
                            if (
                                file.date_time
                                <= extracted_by_name[extract_to_name].date_time
                            ):
                                continue
                        top_zip.extract(file, student_work_path)
                        extracted_by_name[extract_to_name] = file

                        # Rename to remove student name/netid from file
                        unpack_old_path = student_work_path / file.filename
                        unpack_new_path = student_work_path / extract_to_name
                        unpack_old_path.rename(unpack_new_path)

                        # Restore timestamp
                        date_time = time.mktime(file.date_time + (0, 0, -1))
                        os.utime(unpack_new_path, (date_time, date_time))
                        continue

                    # Otherwise this is a zip within zip. Open it up and collect contained files
                    with zipfile.ZipFile(top_zip.open(file)) as inner_zip:
                        for file2 in inner_zip.infolist():
                            if file2.is_dir():
                                continue
                            count_by_filename[file2.filename] += 1

                            # If we've already extracted a file of this name, don't overwrite if older
                            if file2.filename in extracted_by_name:
                                if (
                                    file2.date_time
                                    <= extracted_by_name[file2.filename].date_time
                                ):
                                    continue

                            inner_zip.extract(file2, student_work_path)
                            extracted_by_name[file2.filename] = file2

                            # Restore timestamp
                            unpack_path = student_work_path / file2.filename
                            date_time = time.mktime(file2.date_time + (0, 0, -1))
                            os.utime(unpack_path, (date_time, date_time))

        # Print what was extracted
        for k in sorted(extracted_by_name.keys()):
            print("  ", k, end=" ")
            if count_by_filename[k] > 1:
                print_color(
                    TermColors.YELLOW,
                    "(" + str(count_by_filename[k]),
                    "versions submitted, using last modified.)",
                )
            else:
                print()

        # Return success if at least one file is obtained
        if len(extracted_by_name) == 0:
            print_color(TermColors.YELLOW, "No submission")
            return False

        return True

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


def _verify_callback_fcn(fcn, item, fcn_extra_args_dict=None, github_configured=False):
    callback_args = [
        "lab_name",
        "item_name",
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
    if github_configured:
        callback_args.append("repo_url")
        callback_args.append("tag")

    # output is always provided (sys.stdout in sequential, temp file in parallel)
    callback_args.append("output")

    callback_args_optional = [
        "section",
        "homework_id",
    ]

    if fcn_extra_args_dict is None:
        fcn_extra_args_dict = {}

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
        if (
            (named_arg not in callback_args)
            and (named_arg not in callback_args_optional)
            and (named_arg not in fcn_extra_args_dict)
        ):
            error(
                "Your callback function",
                "(" + fcn.__name__ + ")",
                "takes a named argument",
                "'" + named_arg + "'",
                "but this is not provided by the grader. Please remove this argument or the grader "
                + "will not be able to call your callback function correctly. Available callback arguments:",
                str(callback_args),
            )
        elif named_arg not in callback_args and named_arg not in fcn_extra_args_dict:
            warning(
                "Your callback function",
                "(" + fcn.__name__ + ")",
                "takes a named argument",
                "'" + named_arg + "'",
                "but this argument is not always provided by the grader.",
                "If it is missing from your grades CSV file this will cause a runtime error.",
                "Please consider use keyword arguments (**kw) instead.",
            )
