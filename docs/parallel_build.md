# Pre-Building Student Code

For labs with slow builds (e.g., FPGA synthesis taking minutes per student), you can pre-build all student submissions before grading. This splits grading into two phases:

1. **Build Phase**: Build all student submissions using `build_only=True`
2. **Run Phase**: Grade interactively using `run_only=True` (builds already done)

This is useful because:
- Builds can run unattended (e.g., overnight or while doing other work)
- Failed builds are identified before you start grading
- Interactive grading is fast since code is already built

## How It Works

Your callback receives `build` and `run` arguments that indicate what operations to perform:

| Mode | `build` | `run` |
|------|---------|-------|
| Normal | `True` | `True` |
| `build_only=True` | `True` | `False` |
| `run_only=True` | `False` | `True` |

### Grading Script Example

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--build", action="store_true", help="Build only")
parser.add_argument("--grade", action="store_true", help="Grade only (run_only)")
args = parser.parse_args()

grader = ygrader.Grader(...)
grader.add_item_to_grade(grading_fcn=grading_handler, ...)

if args.build:
    # Phase 1: Build all submissions
    grader.set_other_options(build_only=True)
elif args.grade:
    # Phase 2: Grade interactively (builds already done)
    grader.set_other_options(run_only=True)
else:
    # Normal mode: build and run for each student sequentially
    pass

grader.run()
```

### Callback Example

```python
def grading_handler(
    student_code_path,
    build=True,
    run=True,
    output=None,
    **kwargs
):
    if output is None:
        output = sys.stdout

    if build:
        # Build phase: compile the student's code
        print("Building...", file=output)
        result = subprocess.run(
            ["make", "all"],
            cwd=student_code_path / "src",
            capture_output=True,
            text=True,
        )
        print(result.stdout, file=output)
        if result.returncode != 0:
            print(result.stderr, file=output)

    if run:
        # Run phase: check results and return deductions
        output_file = student_code_path / "src" / "output.bin"
        if not output_file.exists():
            return [("Build failed - no output", -10)]
        
        # Run tests, check results, return deductions
        result = check_output(output_file)
        if not result.passed:
            return [("Test failed", -5)]
        
        return []  # No deductions
```

### Usage

```bash
# Phase 1: Build all (can run unattended)
python run_grader.py lab1 --build

# Phase 2: Grade interactively
python run_grader.py lab1 --grade
```

## Parallel Builds

By default, `build_only` mode processes students sequentially. For faster builds, you can enable parallel execution by setting `parallel_workers`:

```python
grader.set_other_options(build_only=True, parallel_workers=25)
```

This will:
1. Clone/fetch all student repositories in parallel
2. Run your grading callback with `build=True` for each student
3. Display a summary of successes and failures
4. Skip any students already graded

### How Parallel Execution Works
- Uses Python's `ThreadPoolExecutor` with the specified number of workers
- Includes a 0.5 second delay between starting the first N workers to avoid overwhelming SSH servers if using remote builds.

### Important: Using the `output` Argument

When running in parallel mode, your callback **must** use the `output` argument for all print statements and subprocess output. The grader passes a file handle to each callback, and writing to this file ensures:

- Output from different students doesn't interleave on the console
- Each student's complete build log is captured in their individual log file
- You can review the full build output later if something fails

**Always use:**
```python
print("Building...", file=output)
print(result.stdout, file=output)
```

**Never use in parallel builds:**
```python
print("Building...")  # Goes to stdout, interleaves with other students
```

If your callback writes directly to `sys.stdout` during parallel execution, the output will be mixed together and difficult to debug.

### Output Handling

Each student's build output is written to a temporary log file:
```
/tmp/ygrader_{netid}_{random}.log
```

The console shows a clean summary:
```
Running parallel build with 25 workers for 85 students...

[DONE] jsmith    - /tmp/ygrader_jsmith_abc123.log
[DONE] mjones    - /tmp/ygrader_mjones_def456.log
[FAIL] rjohnson  - Build error: make failed - /tmp/ygrader_rjohnson_ghi789.log

Completed: 82 success, 2 failed, 1 skipped
```

### Log Files

Each student gets a temporary log file containing:
- Git clone/fetch output
- Remote SSH commands and their output
- Any error messages


The log file path is shown next to each student's result. To view:

```bash
cat /tmp/ygrader_jsmith_abc123.log
```

Or open in VS Code by clicking the path in the terminal (if your terminal supports it).

