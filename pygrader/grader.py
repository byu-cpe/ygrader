import pathlib
import enum
import sys
import csv
import zipfile
import time
import os
import shutil
from typing import Callable

from . import grades_csv
from . import utils, student_repos

from .utils import print_color, TermColors, error


class CodeSource(enum.Enum):
    """ Used to indicate whether the student code is submitted via LearningSuite or Github """

    LEARNING_SUITE = 1
    GITHUB = 2


class Grader:
    """ Grader class """

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
        format_code: bool = False,
        build_only: bool = False,
        run_only: bool = False,
        allow_rebuild: bool = True,
        allow_rerun: bool = True,
    ):

        """
        Parameters
        ----------
        name: str
            Name of the grading process (ie. 'passoff' or 'coding_standard').  This is just used for folder naming.
        lab_name: str
            Name of the lab that you are grading (ie. 'lab3').  This is passed back to your run_on_* functions.
        points: list of int
            Number of points the graded milestone(s) are worth.
        work_path: pathlib.Path
            Path to directory where student files will be placed.  For example, if you pass in '.', then student code would be placed in './lab3'
        code_source: CodeSource
            Type of source code location, ie. Learning Suite zip file or Github
        grades_csv_path: pathlib.Path
            Path to CSV file with student grades exported from LearningSuite.  You need to export netid, first and last name, and any grade columns you want to populate.
        grades_col_names: list of str
            Names of student CSV columns for milestones that will be graded.
        run_on_milestone: Callable
            Called on each graded milestone.  Arguments provided (I suggest you make use of \*\*kwargs as I may need to pass more information back in the future):

          * lab_name: (str) The lab_name provided earlier.
          * milestone_name: (str) Grade CSV column name of milestone to run
          * student_code_path (pathlib.Path)  The page to where the student files are stored.
          * build: (bool) Whether files should be built/compiled.
          * run: (bool) Whether milestone should be run.
          * first_names: (list) List of first name of students in the group
          * last_names: (list) List of last names of students in the group
          * net_ids: (list) List of net_ids of students in the group.
          * Return value: (str)
            When this function returns, the program will ask the user for a grade input.  If you return a string from this function, it will print that message first.  This can be a helpful reminder to the TAs of a grading rubric, things they should watch out for, etc.
        run_on_lab: Optional[Callable]
            This function will be called once, before any milestones are graded.  Useful for doing one-off actions before running each milestone, or if you are not grading any milestones and only running in analysis mode. This function callback takes the same arguments as the one provided to 'run_on_milestone', except it does not have a 'milestone_name' argument.
        github_csv_path:  Optional[pathlib.Path]
            Path to CSV file with Github URL for each student.  There must be a 'Net ID' column name.  One way to get this is to have a Learning Suite quiz where students enter their Github URL, and then export the results.
        github_csv_col_name: Optional[str]
            Column name in the github_csv_path CSV file that should be used as the Github URL.  Note: This column name may be fixed for every lab, or it could vary, which allows you to handle Github groups, and even students changing groups between labs.
        github_tag: Optional[str]
            Tag that holds this students submission for this lab.
        learning_suite_submissions_zip_path: Optional[pathlib.Path]
            Path to zip file with all learning suite submissions.  This zip file should contain one zip file per student (if student has multiple submissions, only the most recent will be used).
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
        """

        self.name = name
        self.lab_name = lab_name

        if not isinstance(points, (list, tuple)):
            error("points must a be list or tuple (points per milestone)")
        self.points = points

        self.work_path = pathlib.Path(work_path)
        if not self.work_path.is_dir():
            error("work_path", self.work_path, "is not a directory")
        self.work_path = self.work_path / (lab_name + "_" + name)

        self.code_source = code_source
        assert isinstance(code_source, CodeSource)

        self.grades_csv_path = pathlib.Path(grades_csv_path)

        if not isinstance(grades_col_names, (list, tuple)):
            error("grades_col_names must be list or tuple (column name per milestone)")
        self.grades_col_names = grades_col_names

        self.github_csv_path = github_csv_path
        self.github_csv_col_name = github_csv_col_name
        self.github_tag = github_tag
        self.learning_suite_submissions_zip_path = learning_suite_submissions_zip_path

        self.run_on_lab = run_on_lab
        self.run_on_milestone = run_on_milestone
        self.format_code = format_code
        self.build_only = build_only
        self.run_only = run_only
        self.allow_rebuild = allow_rebuild
        self.allow_rerun = allow_rerun

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

        if not (self.allow_rebuild or self.allow_rerun):
            error("At least one of allow_rebuild and allow_rerun needs to be True.")

    def run(self):
        """ Call this to start (or resume) the grading process """

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

            # Get student code from zip or github
            if not self._get_student_code(index, row, student_work_path):
                continue

            # Format student code
            if self.format_code:
                print_color(TermColors.BLUE, "Formatting code")
                utils.clang_format_code(student_work_path)

            # variable to flag if build needs to be performed
            # initialize to False as the code must be built at least once
            # (will be false if TA chooses to just re-run and not re-build)
            build = True

            if self.run_on_lab is not None:
                try:
                    self.run_on_lab(
                        lab_name=self.lab_name,
                        student_code_path=student_work_path,
                        build=build and not self.run_only,
                        run=not self.build_only,
                        first_names=first_names,
                        last_names=last_names,
                        net_ids=net_ids,
                    )
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
                    msg = ""
                    # Build it and run
                    msg = None
                    if self.run_on_milestone is not None:
                        try:
                            msg = self.run_on_milestone(
                                lab_name=self.lab_name,
                                milestone_name=grade_col_name,
                                student_code_path=student_work_path,
                                build=build and not self.run_only,
                                run=not self.build_only,
                                first_names=first_names,
                                last_names=last_names,
                                net_ids=net_ids,
                            )
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
                    try:
                        score = self._get_score(
                            concated_names,
                            self.lab_name + "-" + grade_col_name,
                            self.points[col_idx],
                            self.allow_rebuild,
                            self.allow_rerun,
                            msg,
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
                            str(self.grades_csv_path), index=False, quoting=csv.QUOTE_ALL
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
            group_name = row["group"]

            # For now, group name will always be net id
            zip_matches = list(self.work_path.glob("*_" + group_name + "_*.zip"))
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
            # For learning suite, I don't currently handle groups, but it could be added fairly easily here.
            # Right now I am just putting them in a group with their Net ID (every student will be in their own group)
            df["group"] = df["Net ID"]
            groupby_column = "group"

        # Group students into their groups
        return df.groupby(groupby_column).agg(lambda x: list(x)).reset_index()

    def _get_student_code(self, index, row, student_work_path):
        if self.code_source == CodeSource.GITHUB:
            # Clone student repo
            print("Student repo url: " + row["github_url"])
            if not student_repos.clone_repo(row["github_url"], self.github_tag, student_work_path):
                return False
        else:
            # Skip if student has no submission
            if (
                self.code_source == CodeSource.LEARNING_SUITE
                and index not in self.df_idx_to_zip_path
            ):
                print_color(TermColors.YELLOW, "No submission")
                return False

            # Unzip student files (if student_dir doesn't alreayd exist) and delete zip
            zip_file = self.df_idx_to_zip_path[index]
            try:
                # Unzip if sutdent work path is empty
                if not list(student_work_path.iterdir()):
                    print(
                        "Unzipping",
                        zip_file.name,
                        "into",
                        student_work_path.relative_to(self.work_path.parent),
                    )
                    with zipfile.ZipFile(zip_file, "r") as zf:
                        zf.extractall(student_work_path)
                    zip_file.unlink()
            except zipfile.BadZipFile:
                print_color(TermColors.RED, "Bad zip file", zip_file)
                return False
        return True

    def _get_score(
        self, names, assignment_name, max_score, allow_rebuild, allow_rerun, extra_message=""
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
            self.work_path.mkdir()