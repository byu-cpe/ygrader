"""Module for handling parent items and sub-items in the grading system."""

import pathlib

import pandas
import yaml

from . import grades_csv
from .utils import sanitize_filename


class ParentItem:
    """Represents a parent item in the grading system."""

    def __init__(self, yaml_path: pathlib.Path):
        self.subitems = []
        self.csv_col_name = None
        self.other_data = {}

        # First make sure the YAML file exists in a directory of the same name
        if yaml_path.suffix != ".yaml":
            raise ValueError("The item_yaml_path must point to a .yaml file.")
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"The specified YAML file does not exist: {yaml_path}"
            )
        if yaml_path.parent.name != yaml_path.stem:
            raise ValueError(
                f"The YAML file must be located in a directory of the same name. Currently {yaml_path} is in {yaml_path.parent}"
            )

        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)

        if "parent_column" not in data:
            raise ValueError(
                f"The YAML file {yaml_path} does not contain a 'parent_column' field."
            )
        self.csv_col_name = data["parent_column"]

        if "columns" not in data:
            raise ValueError(
                f"The YAML file {yaml_path} does not contain a 'columns' field."
            )

        for subitem_data in data["columns"]:
            if "name" not in subitem_data:
                raise ValueError(
                    f"A sub-item in {yaml_path} is missing the 'name' field."
                )
            if "points" not in subitem_data:
                raise ValueError(
                    f"The sub-item '{subitem_data.get('name', '<unknown>')}' in {yaml_path} is missing the 'points' field."
                )
            name = subitem_data["name"]
            points = subitem_data["points"]

            # Collect any other fields beyond 'name' and 'points'
            other_data = {
                k: v for k, v in subitem_data.items() if k not in ("name", "points")
            }
            self.subitems.append(SubItem(yaml_path.parent, name, points, other_data))

        # Parse any other data in the YAML file beyond 'parent_column' and 'columns'
        self.other_data = {
            k: v for k, v in data.items() if k not in ("parent_column", "columns")
        }

    def get_subitem(self, name: str):
        """Get a sub-item by name"""
        for subitem in self.subitems:
            if subitem.name == name:
                return subitem
        raise ValueError(f"Sub-item with name '{name}' not found.")


class SubItem:
    """Represents a sub-item in the grading system."""

    def __init__(
        self, dir_path: pathlib.Path, name: str, points: float, other_data: dict = None
    ):
        self.name = name
        self.filename = sanitize_filename(name)
        self.csv_path = dir_path / "subitems" / f"{self.filename}.csv"
        self.points = points
        self.other_data = other_data if other_data is not None else {}


def generate_subitem_csvs(grades_csv_path, item_yaml_path) -> None:
    """Generate CSV files for sub-items based on the provided item YAML path."""
    item_yaml_path = pathlib.Path(item_yaml_path)
    parent_item = ParentItem(item_yaml_path)
    # grader = Grader("", grades_csv_path)

    grades_df = grades_csv.parse_and_check(grades_csv_path, [parent_item.csv_col_name])

    # Create subitems subdirectory
    subitems_dir = item_yaml_path.parent / "subitems"
    subitems_dir.mkdir(exist_ok=True)

    overwrite_all = False
    for subitem in parent_item.subitems:
        subitem_csv_path = subitems_dir / f"{subitem.filename}.csv"

        # Check if file already exists and ask user if they want to overwrite
        if subitem_csv_path.exists() and not overwrite_all:
            response = input(
                f"{subitem_csv_path} already exists. Overwrite (you may lose grades)? (y/n/all): "
            )
            if response.lower() == "all":
                overwrite_all = True
            elif response.lower() not in ("y", "yes"):
                print(f"Skipping {subitem_csv_path}")
                continue

        print(f"Generating {subitem_csv_path}...")

        # Create a DataFrame with Net ID, Last Name, First Name columns and subitem column
        subitem_df = pandas.DataFrame()
        subitem_df["Net ID"] = grades_df["Net ID"]
        subitem_df["Last Name"] = grades_df["Last Name"]
        subitem_df["First Name"] = grades_df["First Name"]
        subitem_df[subitem.name] = ""

        subitem_df.to_csv(subitem_csv_path, index=False)

        # Make sure this is a valid file for grading
        grades_csv.parse_and_check(subitem_csv_path, [subitem.name])
