import pandas
import re
import numpy

from .utils import error


def parse_and_check(grades_csv_path, grades_col_names):
    grades_df = pandas.read_csv(grades_csv_path)
    check_csv_column_names(grades_df, grades_col_names)
    return grades_df


def check_csv_column_names(df, expected_grade_col_names):
    """This function checks that the provided CSV file has the correct number of coulumns,
    and that each column name matches the expected values for the lab being graded"""

    # Check that column [0] is last name
    if df.columns[0] != "Last Name":
        error("Column 0 of grades CSV must be 'Last Name'")

    # Check that column [1] is first name
    if df.columns[1] != "First Name":
        error("Column 1 of grades CSV must be 'First Name'")

    # Check that column [2] is Net ID
    if df.columns[2] != "Net ID":
        error("Column 2 of grades CSV must be 'Net ID'")

    for expected_col_name in expected_grade_col_names:
        if expected_col_name not in df.columns:
            error("Grades CSV does not contain column with name", expected_col_name)


# Filter down to only those students that need a grade
def filter_need_grade(df, expected_grade_col_names):
    filtered_df = df[df[df.columns & expected_grade_col_names].isnull().any(1)]
    return filtered_df


def match_to_github_url(df_needs_grade, github_csv_path, github_csv_col_name):
    def _github_url_to_ssh(github_url):
        # Legacy -- non-lab 3 urls are only usernames -- fix this in future year quizzes
        if not "github.com" in github_url:
            github_url = "git@github.com:byu-ecen427-classroom/427-labs-" + github_url + ".git"

        m = re.match("https://github.com/(.*?)(?:\.git)*$", github_url)
        if m:
            return "git@github.com:" + m.group(1) + ".git"
        else:
            return github_url

    df_github = pandas.read_csv(github_csv_path)

    # Strip whitespace from CSV header names
    df_github.rename(columns=lambda x: x.strip(), inplace=True)

    # Rename appropriate column to github url
    df_github.rename(columns={github_csv_col_name: "github_url"}, inplace=True)

    # Filter down to relevant columns
    df_github = df_github[["Net ID", "github_url"]]

    # Transform github public URLs to SSH URLs
    df_github["github_url"] = df_github["github_url"].apply(lambda x: _github_url_to_ssh(x))

    # Merge with student dataframe (inner merge will drop students without github URL)
    df_joined = df_needs_grade.merge(df_github)

    return df_joined


def find_idx_for_netid(df, netid):
    matches = df.index[df["Net ID"] == netid].tolist()
    if len(matches) != 1:
        error("Could not find netid =", netid, "(find_idx_for_netid)")
    return matches[0]


def num_grades_needed_per_milestone(row, grades_col_names):
    ret = []
    for grades_col_name in grades_col_names:
        n = 0
        for grade in row[grades_col_name]:
            if numpy.isnan(grade):
                n += 1
        ret.append(n)
    return ret