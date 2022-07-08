# Introduction



The package is designed to help you write grading scripts.  The main idea behind the package is that it removes all of the overhead that is common between grading different classes (extracing student code into their own folder, updating grade CSV files, etc), and allows you to focus on just writing scripts for running student code in your class' environment.  This framework does not assume anything about the student's code structure; it should be equally helpful for grading hardware or software labs.

## Example

This example (available on [github](https://github.com/byu-cpe/ygrader-example)), demonstrates a very simple use of ygrader to grade lab reports.
The [example.py](https://github.com/byu-cpe/ygrader-example/blob/main/example.py) file:
```python
import sys
import ygrader

def my_callback(student_code_path, lab_name, **kw):

    # Print the student's lab report
    lab_report_path = student_code_path / "lab_report.txt"
    if lab_report_path.is_file():
        print(open(lab_report_path).read())
    else:
        raise ygrader.CallbackFailed("Missing lab_report.txt")

# Configure and run the grader
grader = ygrader.Grader("lab1", "learning_suite/grades.csv", "lab1_labreport", 10)
grader.set_callback_fcn(my_callback)
grader.set_submission_system_learning_suite("learning_suite/lab1_submissions.zip")
grader.run()
```

In this example, the *lab1_submissions.zip* would have been batch downloaded from Learning Suite, and contains zip files of student submissions.  In this example, the student *Mike Smith* has submitted a lab report, while *Steve Jones'* submission is missing the *lab_report.txt* file, and *Anna Wilkinson* didn't submit anything.  

When you run the example you should see the following interactive output:

![test](example_screenshot.png)

This is an example of a very simple callback routine that just prints out a text file and asks the TA to enter a grade.  You can make your callbacks as complex as you want, such as compiling and running hardware or software, running simulations, or opening other programs.  You can have the TA enter a grade manually, or you can automatically calculate and return a grade from your callback function.

## Major Features

* The package can work with student code submitted via zip files (ie using Learning Suite), *or* with student code on Github.  
* Grade multiple items at once (multiple columns in Learning Suite). This can allow you to run different tests each worth different number of points.
* Team-based assignments.
* Grades are updated in the CSV files as soon as you enter them, meaning you can Ctrl+C and kill the grading at any point, and re-run to continue where you left off.
* Can be run in analysis mode, where student code is fetched and callbacks are made, but no grades are entered.  This is useful for things like collecting stats, running plagarism checkers, etc. 



## How to Use This
See [](usage.md)


