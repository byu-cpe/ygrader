# Welcome to pygrader’s documentation!

The package is designed to help you write grading scripts.  The main idea behind the package is that it removes all of the overhead that is common between grading different classes (extracing student code into their own folder, updating grade CSV files, etc), and allows you to focus on just writing scripts for running student code in your class’ environment.  This framework does not assume anything about the student’s code structure; it should be equally helpful for grading hardware or software labs.

## Grading Flow

When you configure the script correctly, the expected flow is:


1. Grade CSV from LearningSuite is parsed, and student grades are tracked in a pandas DataFrame


2. Students are filtered down to only those that still need a grade for the assignment.


3. Students are formed into their groups (groups of 1 for individual assignments)


4. For each student:


    * Student code is retrieved (from Github or Learning suite zip file) and copied into a per-group working folder.


    * *Callbacks are made to your code*, where you can build and run the student’s code.


    * The TA is prompted to enter a grade.  They can optionally rebuild and rerun the students code, or skip to the next student without entering a grade.


    * Grade CSV is updated with grade for all group members.

In the above process, *you will only need to write the callback code to build and run the student’s code*.

## Major Features


* The package can work with student code submitted via zip files (ie using Learning Suite), *or* with student code on Github.


* Supports labs with multiple different grade columns in Learning Suite (referred to as *milestones* in this documentation).  This can allow you to run different tests each worth different number of points.


* Supports team-based assignments (currently via Github submission only, but I could fairly easily extend this to Learning Suite submissions if there is demand).


* Grades are updated in the CSV files as soon as you enter them, meaning you can Ctrl+C the grading at any point, and re-run to continue where you left off.


* Can be run in analysis mode, where student code is fetched and callbacks are made, but no grades are entered.  This is useful for things like collecting stats, running plagarism checkers, etc. (To use this option, provide an empty list to ‘grades_col_names’)

## How to Use This

The typical usage model is that you create your own grader repository for your class, and would add this repository as a submodule.  In your repository you would store your CSVs exported from Learning Suite, and student code submissions (if using Learning Suite submission and not Github).

You would then create any grading scripts you like (ie in 330 we have a grading script for pass-off, and one for coding standard).  In my code, these scripts take a single command-line argument, which indicates which lab to grade.  An example:

```
./run_passoff_grader.py lab3
```

This script would then create an instance of the `Grader` class below, passing in the several required configuration options, followed by calling `run()`. The configuration options you pass in will likely depend on the lab you are grading.  For example, in my code, I typically have functions that take in the lab name, and then return the different configuration options.

```
def main():
  # Command-line arguments
  parser = argparse.ArgumentParser()
  parser.add_argument("lab_name", choices=[l.name for l in labs.lab_list])
  args = parser.parse_args()

  # Find lab object
  lab = labs.find_lab(args.lab_name)

  zip_path = SUBMISSIONS_PATH / (lab.name + ".zip")
  csv_path = LEARNING_SUITE_PATH / (lab.name + "_passoff.csv")

  grader = Grader(
      name="passoff",
      lab_name=lab.name,
      points=[milestone.max_score for milestone in lab.milestones],
      work_path=ROOT_PATH,
      code_source=CodeSource.LEARNING_SUITE,
      grades_csv_path=csv_path,
      grades_col_names=[milestone.gradebook_col_name for milestone in lab.milestones],
      run_on_milestone=run_milestone,
      run_on_lab=run_lab,
      learning_suite_submissions_zip_path=zip_path,
      format_code=True,
      allow_rerun=False,
  )

  grader.run()
```

The bulk of your code will be placed in your callback functions that will build and run each student’s code.

I typically give TAs access to this grading repo, and put them in charge of both exporting CSVs from Learning Suite, and importing them after grading.

## Examples


* ECEN 330 grader (Learning Suite submission style): [https://github.com/byu-cpe/ecen330_grader](https://github.com/byu-cpe/ecen330_grader)


    * [https://github.com/byu-cpe/ecen330_grader/blob/master/run_passoff_grader.py](https://github.com/byu-cpe/ecen330_grader/blob/master/run_passoff_grader.py)


    * [https://github.com/byu-cpe/ecen330_grader/blob/master/run_coding_standard_grader.py](https://github.com/byu-cpe/ecen330_grader/blob/master/run_coding_standard_grader.py)


    * [https://github.com/byu-cpe/ecen330_grader/blob/master/run_moss.py](https://github.com/byu-cpe/ecen330_grader/blob/master/run_moss.py) (Analysis mode only)


* ECEN 427 grader (Github submission style): [https://github.com/byu-cpe/ecen427_grader](https://github.com/byu-cpe/ecen427_grader)


    * [https://github.com/byu-cpe/ecen427_grader/blob/master/run_passoff.py](https://github.com/byu-cpe/ecen427_grader/blob/master/run_passoff.py)


    * [https://github.com/byu-cpe/ecen427_grader/blob/master/run_coding_standard.py](https://github.com/byu-cpe/ecen427_grader/blob/master/run_coding_standard.py)

## Class Documentation


### class pygrader.grader.CodeSource(value)
Used to indicate whether the student code is submitted via LearningSuite or Github


### class pygrader.grader.Grader(name: str, lab_name: str, points: list, work_path: pathlib.Path, code_source: pygrader.grader.CodeSource, grades_csv_path: pathlib.Path, grades_col_names: list, run_on_milestone: Callable[[str, pathlib.Path], None] = None, run_on_lab: Callable[[str, pathlib.Path], None] = None, github_csv_path: pathlib.Path = None, github_csv_col_name: list = [], github_tag: str = None, learning_suite_submissions_zip_path: pathlib.Path = None, format_code: bool = False, build_only: bool = False, allow_rebuild: bool = True, allow_rerun: bool = True)
Grader class


* **Parameters**

    
    * **name** (*str*) – Name of the grading process (ie. ‘passoff’ or ‘coding_standard’).  This is just used for folder naming.


    * **lab_name** (*str*) – Name of the lab that you are grading (ie. ‘lab3’).  This is passed back to your run_on_\* functions.


    * **points** (*list of int*) – Number of points the graded milestone(s) are worth.


    * **work_path** (*pathlib.Path*) – Path to directory where student files will be placed.  For example, if you pass in ‘.’, then student code would be placed in ‘./lab3’


    * **code_source** (*CodeSource*) – Type of source code location, ie. Learning Suite zip file or Github


    * **grades_csv_path** (*pathlib.Path*) – Path to CSV file with student grades exported from LearningSuite.  You need to export netid, first and last name, and any grade columns you want to populate.


    * **grades_col_names** (*list of str*) – Names of student CSV columns for milestones that will be graded.


    * **run_on_milestone** (*Callable*) – Called on each graded milestone.  Arguments provided (I suggest you make use of \*\*kwargs as I may need to pass more information back in the future):


        * lab_name: (str) The lab_name provided earlier.


        * milestone_name: (str) Grade CSV column name of milestone to run


        * student_path (pathlib.Path)  The page to where the student files are stored.


        * build: (bool) Whether files should be built/compiled.


        * run: (bool) Whether milestone should be run.


        * first_names: (list) List of first name of students in the group


        * last_names: (list) List of last names of students in the group


        * net_ids: (list) List of net_ids of students in the group.


        * Return value: (str)
    When this function returns, the program will ask the user for a grade input.  If you return a string from this function, it will print that message first.  This can be a helpful reminder to the TAs of a grading rubric, things they should watch out for, etc.



    * **run_on_lab** (*Optional**[**Callable**]*) – This function will be called once, before any milestones are graded.  Useful for doing one-off actions before running each milestone, or if you are not grading any milestones and only running in analysis mode. This function callback takes the same arguments as the one provided to ‘run_on_milestone’, except it does not have a ‘milestone_name’ argument.


    * **github_csv_path** (*Optional**[**pathlib.Path**]*) – Path to CSV file with Github URL for each student.  There must be a ‘Net ID’ column name.  One way to get this is to have a Learning Suite quiz where students enter their Github URL, and then export the results.


    * **github_csv_col_name** (*Optional**[**str**]*) – Column name in the github_csv_path CSV file that should be used as the Github URL.  Note: This column name may be fixed for every lab, or it could vary, which allows you to handle Github groups, and even students changing groups between labs.


    * **github_tag** (*Optional**[**str**]*) – Tag that holds this students submission for this lab.


    * **learning_suite_submissions_zip_path** (*Optional**[**pathlib.Path**]*) – Path to zip file with all learning suite submissions.  This zip file should contain one zip file per student (if student has multiple submissions, only the most recent will be used).


    * **format_code** (*Optional**[**bool**]*) – Whether you want the student code formatted using clang-format


    * **build_only** (*Optional**[**bool**]*) – Whether you only want to build and not run/grade the students code.  This will be passed to your callback function, and is useful for labs that take a while to build.  You can build all the code in one pass, then return and grade the code later.


    * **allow_rebuild** (*Optional**[**bool**]*) – When asking for a grade, the program will normally allow the grader to request a “rebuild and run”.  If your grader doesn’t support this, then set this to False.


    * **allow_rerun** (*Optional**[**bool**]*) – When asking for a grade, the program will normally allow the grader to request a “re-run only (no rebuld)”. If your grader doesn’t support this, then set this to False.  At least one of ‘allow_rebuild’ and ‘allow_rerun’ must be True.



#### run()
Call this to start (or resume) the grading process
