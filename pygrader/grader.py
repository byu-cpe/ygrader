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

from . import grades_csv
from . import utils, student_repos

from .utils import CallbackFailed, print_color, TermColors, error


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
        points: list,
        work_path: pathlib.Path,
        code_source: CodeSource,
        grades_csv_path: pathlib.Path,
        grades_col_names: list,
        run_on_milestone: Callable[[str, pathlib.Path], None] = None,
        run_on_lab: Callable[[str, pathlib.Path], None] = None,
        github_csv_path: pathlib.Path = None,
        github_csv_col_name: str = None,
        github_tag: str = None,
        learning_suite_submissions_zip_path: pathlib.Path = None,
        learning_suite_groups_csv_path: pathlib.Path = None,
        learning_suite_groups_csv_col_name: str = None,
        format_code: bool = False,
        build_only: bool = False,
        run_only: bool = False,
        allow_rebuild: bool = True,
        allow_rerun: bool = True,
        help_msg: str = None,
    ):

        """
        Parameters
        ----------
        name: str
            Name of the grading process (ie. 'passoff' or 'coding_standard').  This is just used for folder naming.
        lab_name: str
            Name of the lab that you are grading (ie. 'lab3').  This is passed back to your run_on_* functions.
        work_path: pathlib.Path
            Path to directory where student files will be placed.  For example, if you pass in '.', then student code would be placed in './lab3'
        grades_csv_path: pathlib.Path
            Path to CSV file with student grades exported from LearningSuite.  You need to export netid, first and last name, and any grade columns you want to populate.
        grades_col_names: str | list of str
            Names of student CSV columns for milestones that will be graded.
        points: int | list of int
            Number of points the graded milestone(s) are worth.
        code_source: CodeSource
            Type of source code location, ie. Learning Suite zip file or Github. If Github, then you need to provide the subsequent github_* arguments.  If Learning Suite, then provide the learning_suite_* arguments.
        github_csv_path:  Optional[pathlib.Path]
            Path to CSV file with Github URL for each student.  There must be a 'Net ID' column name.  One way to get this is to have a Learning Suite quiz where students enter their Github URL, and then export the results.
        github_csv_col_name: Optional[str]
            Column name in the github_csv_path CSV file that should be used as the Github URL.  Note: This column name may be fixed for every lab, or it could vary, which allows you to handle Github groups, and even students changing groups between labs.
        github_tag: Optional[str]
            Tag that holds this students submission for this lab.
        learning_suite_submissions_zip_path: Optional[pathlib.Path]
            Path to zip file with all learning suite submissions.  This zip file should contain one zip file per student (if student has multiple submissions, only the most recent will be used).
        learning_suite_groups_csv_path: Optional[pathlib.Path]
            If you have groups, this arguments points to a CSV file that contains group names.
        learning_suite_groups_csv_col_name: Optional[str]
            If you have groups, this arguments provides the column name to use for the group.
        run_on_milestone: Callable
            This is the main callback function that you should provide to build, run and/or evaluate the student's file.  You can do anything you like in this function (compile and run software, build bitstreams, program boards, etc).

            The callback will be called on each graded milestone.  Your callback function will be provided with several arguments (I suggest you make use of \*\*kwargs as I may need to pass more information back in the future):

          * lab_name: (str) The lab_name provided earlier.
          * milestone_name: (str) Grade CSV column name of milestone to run
          * student_code_path (pathlib.Path)  The page to where the student files are stored.
          * build: (bool) Whether files should be built/compiled.
          * run: (bool) Whether milestone should be run.
          * first_names: (list) List of first name of students in the group
          * last_names: (list) List of last names of students in the group
          * net_ids: (list) List of net_ids of students in the group.
          * section: (str) Student section number, assuming 'Section Number' was contained in grades_csv exported from Learning Suite.
          * homework_id: (str) Student homework ID, assuming 'Course Homework ID' was contained in grades_csv exported from Learning Suite.
          * Return value: (int)
            If you return nothing, the default script behavior is that the program will ask the user to input a grade.  If you already know the grade you want to assign, and don't want to prompt the user, just return the grade from this callback.

        run_on_lab: Optional[Callable]
            This is an additional callback function, but will only be called once, even if you are grading multiple milestones.  It will be called before any milestones are graded.  This is useful for doing one-off actions before running each milestone, or if you are not grading any milestones and only running in analysis mode. This function callback takes the same arguments as the one provided to 'run_on_milestone', except it does not have a 'milestone_name' argument, and you should not return any value.  If you only have single milestone to grade, you can use either callback method, although if you want to return a grade, you will need to use run_on_milestone.

        Other Parameters
        ----------
        format_code: Optional[bool]
            Whether you want the student code formatted using clang-format
        build_only: Optional[bool]
            Whether you only want to build and not run/grade the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.
        run_only: Optional[bool]
            Whether you only want to run/grade and not build the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.
        allow_rebuild: Optional[bool]
            When asking for a grade, the program will normally allow the grader to request a "rebuild and run".  If your grader doesn't support this, then set this to False.
        allow_rerun: Optional[bool]
            When asking for a grade, the program will normally allow the grader to request a "re-run only (no rebuld)". If your grader doesn't support this, then set this to False.  At least one of 'allow_rebuild' and 'allow_rerun' must be True.
        help_msg: Optional[str]
            When the script asks the user for a grade, it will print this message first.  This can be a helpful reminder to the TAs of a grading rubric, things they should watch out for, etc. This can be provided as a single string or a list of strings if there is a different message for each milestone.
        """

        self.name = name
        self.lab_name = lab_name

        if not isinstance(points, (list, tuple)):
            points = [points]
        self.points = points

        self.work_path = pathlib.Path(work_path)
        self.work_path = self.work_path / (lab_name + "_" + name)

        self.code_source = code_source
        assert isinstance(code_source, CodeSource)

        self.grades_csv_path = pathlib.Path(grades_csv_path)

        if not isinstance(grades_col_names, (list, tuple)):
            grades_col_names = [grades_col_names]
        self.grades_col_names = grades_col_names

        self.github_csv_path = github_csv_path
        self.github_csv_col_name = github_csv_col_name
        self.github_tag = github_tag
        self.learning_suite_submissions_zip_path = learning_suite_submissions_zip_path
        self.learning_suite_groups_csv_path = learning_suite_groups_csv_path
        self.learning_suite_groups_csv_col_name = learning_suite_groups_csv_col_name

        self.run_on_lab = run_on_lab
        self.run_on_milestone = run_on_milestone
        self.format_code = format_code
        self.build_only = build_only
        self.run_only = run_only
        self.allow_rebuild = allow_rebuild
        self.allow_rerun = allow_rerun
        self.help_msg = help_msg

        if self.grades_csv_path is not None:
            utils.check_file_exists(self.grades_csv_path)

        if self.code_source == CodeSource.GITHUB:
            if self.github_csv_path is None:
                error("You must specify the github_csv_path argument if using CodeSource.GITHUB")
            if self.github_csv_col_name is None:
                error(
                    "You must specify the github_csv_col_name argument if using CodeSource.GITHUB"
                )
            if self.github_tag is None:
                error("You must specify the github_tag argument if using CodeSource.GITHUB")
            utils.check_file_exists(self.github_csv_path)
        elif self.code_source == CodeSource.LEARNING_SUITE:
            if self.learning_suite_submissions_zip_path is None:
                error(
                    "You must specify the learning_suite_submissions_zip_path argument if using CodeSource.LEARNING_SUITE"
                )
            utils.check_file_exists(self.learning_suite_submissions_zip_path)

            if self.learning_suite_groups_csv_path and not self.learning_suite_groups_csv_col_name:
                error(
                    "If you provide a learning_suite_groups_csv_path, you must provide a column name (learning_suite_groups_csv_col_name)"
                )

        if not (self.allow_rebuild or self.allow_rerun):
            error("At least one of allow_rebuild and allow_rerun needs to be True.")

        # Check that # of CSV columns to grade matches # of points list
        if len(self.grades_col_names) != len(self.points):
            error(
                "List length of grades_col_names (",
                len(self.grades_col_names),
                ") does not match length of points (",
                len(self.points),
                ")",
            )

        # If help message is a single string, duplicate to each milestone
        if isinstance(self.help_msg, str) or self.help_msg is None:
            self.help_msg = [self.help_msg] * len(self.grades_col_names)

    def run(self):
        """Call this to start (or resume) the grading process"""

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

        # Add column for group name to DataFrame
        # For GitHub sources, the group name is the github URL
        grouped_df = self._group_students(student_grades_df)

        # Create work path
        self._create_work_path()

        if self.code_source == CodeSource.LEARNING_SUITE:
            # Unzip submissions and map groups to their submission
            self._unzip_submissions()
            self._build_df_idx_to_zip_map(grouped_df)

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

    def _build_df_idx_to_zip_map(self, df):
        # Map dataframe index to student zip file
        self.df_idx_to_zip_path = {}

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

            self.df_idx_to_zip_path[index] = zip_matches[0]

    def _group_students(self, df):
        if self.code_source == CodeSource.GITHUB:
            # For Github source, group name is simply github URL
            df = grades_csv.match_to_github_url(df, self.github_csv_path, self.github_csv_col_name)

            df_needs_grades = grades_csv.filter_need_grade(df, self.grades_col_names)

            # grades_needed_github_df = grades_csv.match_to_github_url(
            #     grades_needed_df, self.github_csv_path, self.github_csv_col_name
            # )
            print_color(
                TermColors.BLUE,
                str(df_needs_grades.shape[0]),
                "of these students have a github URL.",
            )
            groupby_column = "github_url"
        else:
            if not self.learning_suite_groups_csv_path:
                df = df.copy()
                df["group_id"] = df["Net ID"]
                groupby_column = "group_id"
            else:
                # Group students
                df = grades_csv.match_to_group(
                    df, self.learning_suite_groups_csv_path, self.learning_suite_groups_csv_col_name
                )

                df_needs_grades = grades_csv.filter_need_grade(df, self.grades_col_names)

                print_color(
                    TermColors.BLUE,
                    str(df_needs_grades.shape[0]),
                    "of these students belong to a group.",
                )

                groupby_column = "group_id"

            # If no groupings are provided, just put the student in a group with their Net ID (every student will be in their own group)

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
            # Skip if student has no submission
            if (
                self.code_source == CodeSource.LEARNING_SUITE
                and index not in self.df_idx_to_zip_path
            ):
                print_color(TermColors.YELLOW, "No submission")
                return False

            # Unzip student files (if student_dir doesn't already exist) and delete zip
            zip_file = self.df_idx_to_zip_path[index]
            try:
                # Unzip if student work path is empty
                if not list(student_work_path.iterdir()):
                    print(
                        "Unzipping",
                        zip_file.name,
                        "into",
                        student_work_path.relative_to(self.work_path.parent),
                    )
                    with zipfile.ZipFile(zip_file, "r") as zf:
                        zf.extractall(student_work_path)
            except zipfile.BadZipFile:
                print_color(TermColors.RED, "Bad zip file", zip_file)
                return False
            return zip_file.stat().st_mtime

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
