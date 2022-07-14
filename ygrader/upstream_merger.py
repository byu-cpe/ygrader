""" Separate script used to merge new changes to base repo into Githug classroom repos."""

import pathlib
import subprocess

import pandas

from . import utils, student_repos
from .utils import TermColors, error, print_color


class UpstreamMerger:
    """
    This class is used to automatically merge in new changes to your upstream repo into each student's repository.
    """

    def __init__(
        self, github_csv_path: pathlib.Path, github_csv_col_name: str, upstream_repo_url: str
    ):
        utils.check_file_exists(github_csv_path)

        self.github_csv_path = github_csv_path
        self.github_csv_col_name = github_csv_col_name
        self.upstream_repo_url = upstream_repo_url

    def run(self):
        """Run the merger process"""
        df = pandas.read_csv(self.github_csv_path)

        if self.github_csv_col_name not in df.columns:
            error(
                "Specified column name", self.github_csv_col_name, "does not exist in the CSV file"
            )
        if "Net ID" not in df.columns:
            error("CSV file does not contain column 'Net ID'")

        tmp_path = pathlib.Path.cwd() / "temp" / "upstream_merge"

        tmp_path.mkdir(exist_ok=True, parents=True)

        for _, row in df.iterrows():
            netid = row["Net ID"]
            print_color(TermColors.PURPLE, netid)

            student_tmp_path = tmp_path / netid
            student_repos.clone_repo(row[self.github_csv_col_name], "main", student_tmp_path)

            # Add remote
            subprocess.run(
                ["git", "remote", "add", "upstream", self.upstream_repo_url],
                cwd=student_tmp_path,
                check=False,
            )

            # Fetch remote
            subprocess.run(
                ["git", "fetch", "upstream"],
                cwd=student_tmp_path,
                check=True,
            )

            # Merge remote
            try:
                subprocess.run(
                    ["git", "merge", "upstream/main", "--no-edit"],
                    cwd=student_tmp_path,
                    check=True,
                )
            except subprocess.CalledProcessError:
                print_color(TermColors.RED, "merge failed.")
                break

            # Push
            subprocess.run(
                ["git", "push"],
                cwd=student_tmp_path,
                check=True,
            )
