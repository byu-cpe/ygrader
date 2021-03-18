#!/usr/bin/python3

import pathlib
import sys

ROOT_PATH = pathlib.Path(__file__).parent.parent
sys.path.append(str(ROOT_PATH))

import argparse

from pygrader import UpstreamMerger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("github_csv_path")
    parser.add_argument("csv_col_name")
    parser.add_argument("upstream_repo_url")
    args = parser.parse_args()

    um = UpstreamMerger(
        pathlib.Path(args.github_csv_path), args.csv_col_name, args.upstream_repo_url
    )

    um.run()


if __name__ == "__main__":
    main()