

# Welcome to pygrader's documentation!

The package is designed to help you write grading scripts.  The main idea behind the package is that it removes all of the overhead that is common between grading different classes (extracing student code into their own folder, updating grade CSV files, etc), and allows you to focus on just writing scripts for running student code in your class' environment.  This framework does not assume anything about the student's code structure; it should be equally helpful for grading hardware or software labs.

## Example




## Grading Flow

When you configure the script correctly, the expected flow is:

1. Grade CSV from LearningSuite is parsed, and student grades are tracked in a pandas DataFrame
1. Students are filtered down to only those that still need a grade for the assignment.
1. Students are formed into their groups (groups of 1 for individual assignments)
1. For each student:

   * Student code is retrieved (from Github or Learning suite zip file) and copied into a per-group working folder.
   * *Callbacks are made to your code*, where you can build and run the student's code.
   * The TA is prompted to enter a grade.  They can optionally rebuild and rerun the students code, or skip to the next student without entering a grade.
   * Grade CSV is updated with grade for all group members.

In the above process, *you will only need to write the callback code to build and run the student's code*.


## Major Features

* The package can work with student code submitted via zip files (ie using Learning Suite), *or* with student code on Github.  
* Supports labs with multiple different grade columns in Learning Suite (referred to as *milestones* in this documentation).  This can allow you to run different tests each worth different number of points.
* Supports team-based assignments (currently via Github submission only, but I could fairly easily extend this to Learning Suite submissions if there is demand).
* Grades are updated in the CSV files as soon as you enter them, meaning you can Ctrl+C the grading at any point, and re-run to continue where you left off.
* Can be run in analysis mode, where student code is fetched and callbacks are made, but no grades are entered.  This is useful for things like collecting stats, running plagarism checkers, etc. (To use this option, provide an empty list to 'grades_col_names')


## How to Use This

The typical usage model is that you create your own grader repository for your class, and would add this repository as a submodule.  In your repository you would store your CSVs exported from Learning Suite, and student code submissions (if using Learning Suite submission and not Github).

You would then create any grading scripts you like (ie in 330 we have a grading script for pass-off, and one for coding standard).  In my code, these scripts take a single command-line argument, which indicates which lab to grade.  An example:

.. code-block:: bash

    ./run_passoff_grader.py lab3


This script would then create an instance of the ``Grader`` class below, passing in the several required configuration options, followed by calling ``run()``. The configuration options you pass in will likely depend on the lab you are grading.  For example, in my code, I typically have functions that take in the lab name, and then return the different configuration options.

Here's a code snippet of ``main()`` from the 330 pass-off script:

.. code-block:: python
  
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


The bulk of your code will be placed in your callback functions that will build and run each student's code.  

I typically give TAs access to this grading repo, and put them in charge of both exporting CSVs from Learning Suite, and importing them after grading.

Examples
########
* ECEN 330 grader (Learning Suite submission style): https://github.com/byu-cpe/ecen330_grader

  * https://github.com/byu-cpe/ecen330_grader/blob/master/run_passoff_grader.py
  * https://github.com/byu-cpe/ecen330_grader/blob/master/run_coding_standard_grader.py
  * https://github.com/byu-cpe/ecen330_grader/blob/master/run_moss.py (Analysis mode only)

* ECEN 427 grader (Github submission style): https://github.com/byu-cpe/ecen427_grader

  * https://github.com/byu-cpe/ecen427_grader/blob/master/run_passoff.py
  * https://github.com/byu-cpe/ecen427_grader/blob/master/run_coding_standard.py

FAQs
####
**Q: Do you recommend creating a new dedicated repository for the class specific grading scripts? Or incorporate into a current lab solutions repository?**

A: Up to you.  I typically use separate grading and solutions repos.  A big reason is because I give the TAs access to the grading repos (they commit grades to CSV files), but I don’t usually give TAs access to our solutions repos.

**Q: How do the TAs access the scripts to run? Do they just checkout your main library and then checkout the repository for the class specific scripts to run?**

A: My usual approach is to make this repo a submodule in your class-specific repo, so TAs would clone your class grade repo.  To get submodule code you need to run `git submodule init` and `git submodule update`, but I usually wrap these into a `make install` Makefile that also installs necessary packages.  (See [427 Install Makefile](https://github.com/byu-cpe/ecen427_grader/blob/master/Makefile)).


Class Documentation
###################

```{eval-rst}
.. automodule:: pygrader.grader
   :members:
```

