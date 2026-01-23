"""Manage the grade CSV file"""

import pandas

from .student_repos import convert_github_url_format
from .utils import TermColors, error, print_color, warning


def parse_and_check(class_list_csv_path, csv_cols):
    """Parse the class list CSV file and check that column names are valid"""
    try:
        grades_df = pandas.read_csv(class_list_csv_path)
    except pandas.errors.EmptyDataError:
        error(
            "Exception: pandas.errors.EmptyDataError.  Is your",
            class_list_csv_path.name,
            "file empty?",
        )
    check_csv_column_names(grades_df, csv_cols)
    return grades_df


def check_csv_column_names(df, expected_grade_col_names):
    """This function checks that the provided CSV file has the correct number of coulumns,
    and that each column name matches the expected values for the lab being graded"""

    required_columns = ["Last Name", "First Name", "Net ID"]
    required_columns += expected_grade_col_names

    for required_column in required_columns:
        if required_column is not None and required_column not in df.columns:
            error(
                "Grades CSV must contain column '" + required_column + "'.",
                "Current columns:",
                list(df.columns),
            )


def filter_need_grade(df, expected_grade_col_names):
    """Filter down to only those students that need a grade"""
    filtered_df = df[
        df[df.columns.intersection(expected_grade_col_names)].isnull().any(axis=1)
    ]
    return filtered_df


def match_to_github_url(
    df_needs_grade, github_csv_path, github_csv_col_name, use_https
):
    """Match students to their github URL"""
    try:
        df_github = pandas.read_csv(github_csv_path, index_col=False)
    except pandas.errors.EmptyDataError:
        error(
            "Exception pandas.errors.EmptyDataError. Is your",
            github_csv_path.name,
            "file empty?",
        )

    # Strip whitespace from CSV header names
    df_github.rename(columns=lambda x: x.strip(), inplace=True)

    if "Net ID" not in df_github.columns:
        error(f"Your github CSV ({github_csv_path}) is missing a 'Net ID' column.")

    # Drop all but Net ID and github URL columns
    df_github = df_github[["Net ID", github_csv_col_name]]

    # Rename appropriate column to github url
    df_github.rename(columns={github_csv_col_name: "github_url"}, inplace=True)

    # Missing from github CSV - Find Net IDs in df_needs_grade that are not in df_github
    missing_netids = df_needs_grade[~df_needs_grade["Net ID"].isin(df_github["Net ID"])]

    # Empty github URL
    missing_df = df_github[df_github.isnull().any(axis=1)]

    if len(missing_netids) or len(missing_df.index):
        warning(
            len(missing_netids.index) + len(missing_df.index),
            "student(s) Net ID are missing a github URL:",
        )

    for _, row in missing_netids.iterrows():
        print_color(" ", TermColors.YELLOW, row["Net ID"])
    for _, row in missing_df.iterrows():
        print_color(" ", TermColors.YELLOW, row["Net ID"])

    df_github = df_github.dropna()

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
    """Read the group names from the group CSV and join them to the original grades CSV"""
    df_groups = pandas.read_csv(groups_csv_path)

    if column_name in df.columns:
        error(
            "The",
            "'" + column_name + "'",
            "column is used for your groups, but this column already exists in your grade CSV file.",
            "The same column name cannot exist in both places.",
        )

    # Rename appropriate column to group
    df_groups.rename(columns={groups_csv_col_name: column_name}, inplace=True)

    # Filter down to relevant columns
    if "Net ID" not in df_groups.columns:
        error(
            "Your group CSV",
            "(" + str(groups_csv_path) + ")",
            "is missing a 'Net ID' column.",
        )
    df_groups = df_groups[["Net ID", column_name]]

    # Merge with student dataframe (inner merge will drop students not in group CSV)
    df_joined = df.merge(df_groups)

    return df_joined


def find_idx_for_netid(df, netid):
    """Find the row index for a given student netid"""
    matches = df.index[df["Net ID"] == netid].tolist()
    if len(matches) != 1:
        error("Could not find netid =", netid, "(find_idx_for_netid)")
    return matches[0]


def get_net_ids(row):
    """Get net IDs from row in grade CSV"""
    return row["Net ID"]


def get_first_names(row):
    """Return first names of group members in the row"""
    return row["First Name"]


def get_last_names(row):
    """Return last names of group members in the row"""
    return row["Last Name"]


def get_concated_names(row):
    """Return a concatenated list of group member names for the row"""
    return ", ".join(
        [
            (first + " " + last + " (" + net_id + ")")
            for (first, last, net_id) in zip(
                get_first_names(row), get_last_names(row), get_net_ids(row)
            )
        ]
    )
