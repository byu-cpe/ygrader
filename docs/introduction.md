# Introduction



The package is designed to help you write grading scripts.  The main idea behind the package is that it removes all of the overhead that is common between grading different classes (extracting student code into their own folder, tracking grading progress, etc.), and allows you to focus on just writing scripts for running student code in your class' environment.  This framework does not assume anything about the student's code structure; it should be equally helpful for grading hardware or software labs.

## Example

First install ygrader:

```bash
pip3 install ygrader
```

Then clone the example repository, available on [github](https://github.com/byu-cpe/ygrader-example), or download the [zip](https://github.com/byu-cpe/ygrader-example/archive/refs/heads/main.zip) and extract.

```
git clone https://github.com/byu-cpe/ygrader-example.git
```

An [example.py](https://github.com/byu-cpe/ygrader-example/blob/main/example.py) file is provided that shows how to run *ygrader*:

```python
import ygrader

def my_callback(student_code_path, lab_name, item_name, **kw):
    print("*** Grading", lab_name, item_name, "***\n")

    lab_report_path = student_code_path / "lab_report.txt"
    if lab_report_path.is_file():
        print(open(lab_report_path).read())
        return None # Interactive deductions
    else:
        raise ygrader.CallbackFailed("Missing lab_report.txt")


grader = ygrader.Grader(
    lab_name="lab1",
    class_list_csv_path="class_list.csv",
)
grader.add_item_to_grade(
    item_name="lab1_labreport",
    grading_fcn=my_callback,
    deductions_yaml_path="deductions/lab1_labreport.yaml",
    max_points=10,
)
grader.set_submission_system_learning_suite("learning_suite/lab1_submissions.zip")
grader.run()
```

In this example, the *lab1_submissions.zip* would have been batch downloaded from Learning Suite, and contains student submissions.  The callback returns `None`, which prompts the TA to enter deductions interactively. If the student's submission is missing, `CallbackFailed` is raised to skip that student.

This is an example of a simple callback routine that prints out a text file and prompts the TA to enter deductions.  You can make your callbacks as complex as you want, such as compiling and running hardware or software, running simulations, or opening other programs.  You can return `None` to prompt the TA to enter deductions manually, or return a list of `(description, points)` tuples to apply deductions automatically.

## Major Features

* The package can work with student files submitted using Learning Suite, *or* with student code on Github.  
* Grade multiple items at once. This can allow you to run different tests, each worth a different number of points.
* Team-based assignments.
* Deductions-based grading: define reusable deduction types that can be applied across students.
* Grading progress is tracked in YAML files, meaning you can Ctrl+C and kill the grading at any point, and re-run to continue where you left off.

## How to Use This
See [](usage.md)


