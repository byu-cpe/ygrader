import pathlib
import enum
import sys
import numpy
import csv
from typing import Union, Callable

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
        run_on_first_milestone: Callable[[str, pathlib.Path], None],
        run_on_each_milestone: Callable[[str, pathlib.Path, bool, bool], None],
        github_csv_path: pathlib.Path = None,
        github_csv_col_name: list = [],
        github_tag: str = None,
        format_code: bool = False,
        build_only: bool = False,
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
        run_on_first_milestone: Function callback.  If you are grading multiple milestones, this function will only be called once.  Useful for doing one-off actions before running each milestone. This function is provided with two arguments:
          * lab_name: (str) The lab_name provided earlier.
          * student_path: (pathlib.Path) The page to where the student files are stored.
        run_on_each_milestone: Function callback, called on each graded milestone.  Arguments provided:
          * lab_name: (str) The lab_name provided earlier.
          * student_path (pathlib.Path)  The page to where the student files are stored.
          * build: (bool) Whether files should be built/compiled.
          * run: (bool) Whether milestone should be run.
        github_csv_path:  pathlib.Path
            Path to CSV file with Github URL for each student.  There must be a 'Net ID' column name.  One way to get this is to have a Learning Suite quiz where students enter their Github URL, and then export the results.
        github_csv_col_name: str
            Column name in the github_csv_path CSV file that should be used as the Github URL.  Note: This column name may be fixed for every lab, or it could vary, which allows you to handle Github groups, and even students changing groups between labs.
        github_tag: str
            Tag that holds this students submission for this lab.
        format_code: bool
            Whether you want the student code formatted using clang-format
        build_only: bool
            Whether you only want to build and not run/grade the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.
        """

        self.name = name
        self.lab_name = lab_name
        self.points = points

        self.work_path = pathlib.Path(work_path)
        if not self.work_path.is_dir():
            error("work_path", self.work_path, "is not a directory")
        self.work_path = self.work_path / (lab_name + "_" + name)
        self.work_path.mkdir(exist_ok=True)

        self.code_source = code_source
        assert isinstance(code_source, CodeSource)

        self.grades_csv_path = pathlib.Path(grades_csv_path)

        # Listify
        self.grades_col_names = grades_col_names
        if isinstance(self.grades_col_names, str):
            self.grades_col_names = [
                self.grades_col_names,
            ]

        self.github_csv_path = github_csv_path
        self.github_csv_col_name = github_csv_col_name
        self.github_tag = github_tag

        self.run_on_first_milestone = run_on_first_milestone
        self.run_on_each_milestone = run_on_each_milestone
        self.format_code = format_code
        self.build_only = build_only

        utils.check_file_exists(self.grades_csv_path)
        utils.check_file_exists(self.github_csv_path)

    def run(self):
        # Print starting message
        print_color(TermColors.BLUE, "Running", self.name, "grader for lab ", self.lab_name)

        # Read in CSV and validate.  Print # students who need a grade
        student_grades_df = grades_csv.parse_and_check(self.grades_csv_path, self.grades_col_names)
        grades_needed_df = grades_csv.filter_need_grade(student_grades_df, self.grades_col_names)
        print_color(
            TermColors.BLUE,
            str(grades_csv.filter_need_grade(grades_needed_df, self.grades_col_names).shape[0]),
            "students need to be graded.",
        )

        # Match df index to github URL
        if self.code_source == CodeSource.GITHUB:
            student_grades_github_df = grades_csv.match_to_github_url(
                student_grades_df, self.github_csv_path, self.github_csv_col_name
            )
            grades_needed_github_df = grades_csv.match_to_github_url(
                grades_needed_df, self.github_csv_path, self.github_csv_col_name
            )
            print_color(
                TermColors.BLUE,
                str(grades_needed_github_df.shape[0]),
                "of these students have a github URL.",
            )
        else:
            raise NotImplementedError

        # Group students into their groups
        if self.code_source == CodeSource.GITHUB:
            df_grouped = (
                student_grades_github_df.groupby("github_url").agg(lambda x: list(x)).reset_index()
            )
        else:
            raise NotImplementedError

        # Loop through all of the students/groups and perform grading
        for index, row in df_grouped.iterrows():
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
            num_group_members_need_grade_per_milestone = grades_csv.num_grades_needed_per_milestone(
                row, self.grades_col_names
            )

            if sum(num_group_members_need_grade_per_milestone) == 0:
                # This student/group is already fully graded
                continue

            # Print name(s) of who we are grading
            print_color(TermColors.PURPLE, "Grading: ", concated_names)
            student_work_path = self.work_path / utils.names_to_dir(
                first_names, last_names, net_ids
            )

            # Get student code
            if self.code_source == CodeSource.GITHUB:
                # Clone student repo

                # Print out the student's repo url
                print("Student repo url: " + row["github_url"])

                if not student_repos.clone_repo(
                    row["github_url"], self.github_tag, student_work_path
                ):
                    continue
            else:
                raise NotImplementedError

            # Format student code
            if self.format_code:
                utils.clang_format_code(student_work_path)

            # variable to flag if build needs to be performed
            # initialize to False as the code must be built at least once
            # (will be false if TA chooses to just re-run and not re-build)
            build = True

            for col_idx, grade_col_name in enumerate(self.grades_col_names):
                if not num_group_members_need_grade_per_milestone[col_idx]:
                    print_color(
                        TermColors.BLUE, "Grade already exists for ", grade_col_name, "(skipping)"
                    )
                    continue

                self.run_on_first_milestone(self.lab_name, student_work_path)

                while True:
                    # Build it and run
                    # runner.run_lab_cmd(args.tag, student_repo_path, build, run=not args.build_only)
                    self.run_on_each_milestone(
                        self.lab_name, student_work_path, build, run=not self.build_only
                    )

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
                        score = utils.get_score(concated_names, self.lab_name, self.points)
                    except KeyboardInterrupt:
                        print_color(TermColors.RED, "\nExiting")
                        sys.exit(0)

                    if score == "s":
                        break
                    elif score == "r":
                        continue
                    elif score == "t":
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
