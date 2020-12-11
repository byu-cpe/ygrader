# Welcome to pygrader’s documentation!

The core module of pygrader


### class pygrader.grader.CodeSource(value)
An enumeration.


### class pygrader.grader.Grader(name: str, lab_name: str, points: list, work_path: pathlib.Path, code_source: pygrader.grader.CodeSource, grades_csv_path: pathlib.Path, grades_col_names: list, run_on_first_milestone: Callable[[str, pathlib.Path], None], run_on_each_milestone: Callable[[str, pathlib.Path, bool, bool], None], github_csv_path: pathlib.Path = None, github_csv_col_name: list = [], github_tag: str = None, format_code: bool = False, build_only: bool = False)
Grader class


* **Parameters**

    
    * **name** (*str*) – Name of the grading process (ie. ‘passoff’ or ‘coding_standard’).  This is just used for folder naming.


    * **lab_name** (*str*) – Name of the lab that you are grading (ie. ‘lab3’).  This is passed back to your run_on_\* functions.


    * **points** (*list of int*) – Number of points the graded milestone(s) are worth.


    * **work_path** (*pathlib.Path*) – Path to directory where student files will be placed.  For example, if you pass in ‘.’, then student code would be placed in ‘./lab3’


    * **code_source** (*CodeSource*) – Type of source code location, ie. Learning Suite zip file or Github


    * **grades_csv_path** (*pathlib.Path*) – Path to CSV file with student grades exported from LearningSuite.  You need to export netid, first and last name, and any grade columns you want to populate.


    * **grades_col_names** (*list of str*) – Names of student CSV columns for milestones that will be graded.


    * **run_on_first_milestone** (*Function callback.  If you are grading multiple milestones**, **this function will only be called once.  Useful for doing one-off actions before running each milestone. This function is provided with two arguments:*) – 
        * lab_name: (str) The lab_name provided earlier.


        * student_path: (pathlib.Path) The page to where the student files are stored.



    * **run_on_each_milestone** (*Function callback**, **called on each graded milestone.  Arguments provided:*) – 
        * lab_name: (str) The lab_name provided earlier.


        * student_path (pathlib.Path)  The page to where the student files are stored.


        * build: (bool) Whether files should be built/compiled.


        * run: (bool) Whether milestone should be run.



    * **github_csv_path** (*pathlib.Path*) – Path to CSV file with Github URL for each student.  There must be a ‘Net ID’ column name.  One way to get this is to have a Learning Suite quiz where students enter their Github URL, and then export the results.


    * **github_csv_col_name** (*str*) – Column name in the github_csv_path CSV file that should be used as the Github URL.  Note: This column name may be fixed for every lab, or it could vary, which allows you to handle Github groups, and even students changing groups between labs.


    * **github_tag** (*str*) – Tag that holds this students submission for this lab.


    * **format_code** (*bool*) – Whether you want the student code formatted using clang-format


    * **build_only** (*bool*) – Whether you only want to build and not run/grade the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.


# Indices and tables


* Index


* Module Index


* Search Page
