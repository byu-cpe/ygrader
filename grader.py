import pathlib
import enum
import sys
import numpy
import csv

from . import grades_csv
from . import utils, student_repos

from .utils import print_color, TermColors, error


class CodeSource(enum.Enum):
    LEARNING_SUITE = 1
    GITHUB = 2


class Grader:
    def __init__(
        self,
        name,
        lab_name,
        points,
        work_path,
        code_source,
        grades_csv_path,
        grades_col_names,
        github_csv_path,
        github_csv_col_name,
        github_tag,
        run_on_first_milestone,
        run_on_each_milestone,
        format_code=False,
        build_only=False,
    ):
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
        print_color(
            TermColors.BLUE,
            str(grades_csv.filter_need_grade(student_grades_df, self.grades_col_names).shape[0]),
            "students need to be graded.",
        )

        # Match df index to github URL
        if self.code_source == CodeSource.GITHUB:
            student_grades_df = grades_csv.match_to_github_url(
                student_grades_df, self.github_csv_path, self.github_csv_col_name
            )
            print_color(
                TermColors.BLUE,
                str(student_grades_df.shape[0]),
                "of these students have a github URL.",
            )
        else:
            raise NotImplementedError

        # Group students into their groups
        if self.code_source == CodeSource.GITHUB:
            df_grouped = (
                student_grades_df.groupby("github_url").agg(lambda x: list(x)).reset_index()
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

            for grade_col_name in self.grades_col_names:
                # Check if student(s) already have a grade for this milestone
                group_needs_grading = False
                group_members_with_grade = 0
                for net_id in net_ids:
                    if numpy.isnan(
                        student_grades_df.at[
                            grades_csv.find_idx_for_netid(student_grades_df, net_id),
                            grade_col_name,
                        ]
                    ):
                        group_needs_grading = True
                    else:
                        group_members_with_grade += 1

                if not group_needs_grading:
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
                    if group_members_with_grade:
                        print_color(
                            TermColors.YELLOW,
                            "  Warning: ",
                            group_members_with_grade,
                            "group members already have a grade for",
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
