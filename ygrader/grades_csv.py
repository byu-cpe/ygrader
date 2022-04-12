import pandas
import re
import numpy

from .student_repos import convert_github_url_format
from .utils import error


def parse_and_check(grades_csv_path, grades_col_names):
    try:
        grades_df = pandas.read_csv(grades_csv_path)
    except pandas.errors.EmptyDataError:
        error(
            "Exception: pandas.errors.EmptyDataError.  Is your", grades_csv_path.name, "file empty?"
        )
    check_csv_column_names(grades_df, grades_col_names)
    return grades_df


def check_csv_column_names(df, expected_grade_col_names):
    """This function checks that the provided CSV file has the correct number of coulumns,
    and that each column name matches the expected values for the lab being graded"""

    required_columns = ["Last Name", "First Name", "Net ID"]
    required_columns += expected_grade_col_names

    for required_column in required_columns:
        if required_column not in df.columns:
            error("Grades CSV must contain column '" + required_column + "'")


# Filter down to only those students that need a grade
def filter_need_grade(df, expected_grade_col_names):
    filtered_df = df[df[df.columns.intersection(expected_grade_col_names)].isnull().any(1)]
    return filtered_df


def match_to_github_url(df_needs_grade, github_csv_path, github_csv_col_name, use_https):
    try:
        df_github = pandas.read_csv(github_csv_path, index_col=False)
    except pandas.errors.EmptyDataError:
        error(
            "Exception pandas.errors.EmptyDataError. Is your", github_csv_path.name, "file empty?"
        )

    # Strip whitespace from CSV header names
    df_github.rename(columns=lambda x: x.strip(), inplace=True)

    # Rename appropriate column to github url
    df_github.rename(columns={github_csv_col_name: "github_url"}, inplace=True)

    # Convert github URLs to https or SSH
    df_github["github_url"] = df_github["github_url"].apply(
        lambda url: convert_github_url_format(url, use_https)
    )

    # Filter down to relevant columns
    df_github = df_github[["Net ID", "github_url"]]

    # Merge with student dataframe (inner merge will drop students without github URL)
    df_joined = df_needs_grade.merge(df_github)

    return df_joined


def add_group_column_from_csv(df, column_name, groups_csv_path, groups_csv_col_name):
    df_groups = pandas.read_csv(groups_csv_path)

    assert column_name not in df.columns

    # Rename appropriate column to group
    df_groups.rename(columns={groups_csv_col_name: column_name}, inplace=True)

    # Filter down to relevant columns
    df_groups = df_groups[["Net ID", column_name]]

    # Merge with student dataframe (inner merge will drop students not in group CSV)
    df_joined = df.merge(df_groups)

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
