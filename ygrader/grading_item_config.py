"""Module for handling LearningSuite column and grade item configs in the grading system."""

import pathlib

import yaml

from .utils import sanitize_filename


class LearningSuiteColumnParseError(Exception):
    """Exception raised when a LearningSuiteColumn YAML file cannot be parsed correctly."""


class LearningSuiteColumn:
    """Represents a grade column configuration in the grading system, with a one-to-one mapping to a LearningSuite column"""

    def __init__(self, yaml_path: pathlib.Path):
        self.items = []
        self.csv_col_name = None
        self.other_data = {}

        # Make sure the YAML file exists
        if yaml_path.suffix != ".yaml":
            raise LearningSuiteColumnParseError(
                "The item_yaml_path must point to a .yaml file."
            )
        if not yaml_path.exists():
            raise LearningSuiteColumnParseError(
                f"The specified YAML file does not exist: {yaml_path}"
            )

        with yaml_path.open("r") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise LearningSuiteColumnParseError(
                f"The YAML file {yaml_path} is empty or invalid."
            )

        if "learning_suite_column" not in data:
            raise LearningSuiteColumnParseError(
                f"The YAML file {yaml_path} does not contain a 'learning_suite_column' field."
            )
        self.csv_col_name = data["learning_suite_column"]

        if "items" not in data:
            raise LearningSuiteColumnParseError(
                f"The YAML file {yaml_path} does not contain an 'items' field."
            )

        for subitem_data in data["items"]:
            if "name" not in subitem_data:
                raise LearningSuiteColumnParseError(
                    f"A sub-item in {yaml_path} is missing the 'name' field."
                )
            if "points" not in subitem_data:
                raise LearningSuiteColumnParseError(
                    f"The sub-item '{subitem_data.get('name', '<unknown>')}' in {yaml_path} is missing the 'points' field."
                )
            name = subitem_data["name"]
            points = subitem_data["points"]

            # Collect any other fields beyond 'name' and 'points'
            other_data = {
                k: v for k, v in subitem_data.items() if k not in ("name", "points")
            }
            self.items.append(
                GradeItemConfig(yaml_path.parent, name, points, other_data)
            )

        # Parse any other data in the YAML file beyond 'learning_suite_column' and 'items'
        self.other_data = {
            k: v for k, v in data.items() if k not in ("learning_suite_column", "items")
        }

    def get_item(self, name: str):
        """Get an item by name"""
        for item in self.items:
            if item.name == name:
                return item
        raise ValueError(f"Item with name '{name}' not found.")


class GradeItemConfig:
    """Represents a grade item configuration in the grading system."""

    def __init__(
        self, dir_path: pathlib.Path, name: str, points: float, other_data: dict = None
    ):
        self.name = name
        self.filename = sanitize_filename(name)
        self.dir_path = dir_path
        self.points = points
        self.other_data = other_data if other_data is not None else {}
        self.feedback_path = dir_path / "items" / f"{self.filename}.yaml"
