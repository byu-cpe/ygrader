# Welcome to pygrader’s documentation!

The core module of pygrader


### class pygrader.grader.CodeSource(value)
An enumeration.


### class pygrader.grader.Grader(name: str, lab_name: str, points: list, work_path: pathlib.Path, code_source, grades_csv_path, grades_col_names, github_csv_path, github_csv_col_name, github_tag, run_on_first_milestone, run_on_each_milestone, format_code=False, build_only=False)
Grader class


* **Parameters**

    
    * **name** (*str*) – Name of this grading process (ie. ‘passoff’ or ‘coding_standard’)


    * **lab_name** (*str*) – Name of the lab that you are grading (ie. ‘lab3’)


    * **points** (*list of ints*) – Number of points the graded milestone(s) are worth.


    * **work_path** (*pathlib.Path*) – Path to directory where student files will be placed.  If you pass in ‘.’, then student code would be placed in ‘./lab3’


    * **code_source** (*CodeSource*) – 


# Indices and tables


* Index


* Module Index


* Search Page
