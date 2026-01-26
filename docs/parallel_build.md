# Parallel Build Mode

The parallel build mode allows you to pre-build all student submissions concurrently before grading. This is useful when:

- Builds are slow (e.g., FPGA synthesis taking minutes per student)
- You want to offload builds to a remote server
- You want to identify build failures before starting interactive grading

## Enabling Parallel Build

Pass `build_only=True` and `parallel_workers=N` to `set_other_options()`:

```python
grader.set_other_options(build_only=True, parallel_workers=25)
grader.run()
```

This will:
1. Clone/fetch all student repositories in parallel
2. Run your grading callback with `build=True` for each student
3. Display a summary of successes and failures
4. Skip any students already graded

After parallel builds complete, run normally to grade.


## How It Works

### Parallel Execution
- Uses Python's `ThreadPoolExecutor` with the specified number of workers
- `parallel_workers` must be explicitly set (no default)
- Includes a 0.5 second delay between starting the first N workers to avoid overwhelming SSH servers

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

### Callback Arguments

Your callback receives `build` and `run` arguments that indicate what operations to perform:

```python
def grading_handler(
    lab_name, 
    student_code_path, 
    build=True,   # False only in run_only mode
    run=True,     # False only in build_only mode
    output=None,  # Log file in parallel mode, stdout otherwise
    **kwargs
):
    if build:
        # Compile/synthesize the student's code
        run_remote_build(...)
    
    if run:
        # Run tests and return deductions
        ...
```

## Two-Phase Grading

For slow builds (e.g., FPGA synthesis), you can split grading into two phases:

1. **Build Phase**: Build all student submissions in parallel using `build_only=True`
2. **Run Phase**: Grade interactively using `run_only=True` (builds already done)

This is useful because:
- Builds can run unattended (e.g., overnight or while doing other work)
- Failed builds are identified before you start grading
- Interactive grading is fast since code is already built

### Grading Script Example

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--build", action="store_true", help="Build only (parallel)")
parser.add_argument("--grade", action="store_true", help="Grade only (run_only)")
args = parser.parse_args()

grader = ygrader.Grader(...)
grader.add_item_to_grade(grading_fcn=grading_handler, ...)

if args.build:
    # Phase 1: Build all submissions in parallel
    grader.set_other_options(build_only=True, parallel_workers=25)
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
    repo_url,
    tag,
    build=True,
    run=True,
    output=None,
    **kwargs
):
    if output is None:
        output = sys.stdout

    if build:
        # Build phase: compile/synthesize on remote server
        print("Building...", file=output)
        run_remote_build(
            remote_host="fpga-server.example.com",
            remote_work_path="/tmp/grading",
            repo_url=repo_url,
            tag=tag,
            commands=[("src", ["make", "all"])],
            files_to_copy=["src/output.bin"],
            student_code_path=student_code_path,
            output=output,
        )

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

## Log Files

### Per-Student Logs
Each student gets a temporary log file containing:
- Git clone/fetch output
- Remote SSH commands and their output
- Any error messages

Log files have restrictive permissions (`0600`) so only you can read them.

### Viewing Logs
The log file path is shown next to each student's result. To view:

```bash
cat /tmp/ygrader_jsmith_abc123.log
```

Or open in VS Code by clicking the path in the terminal (if your terminal supports it).

## Troubleshooting

### Too Many SSH Connections
If you see SSH connection failures, reduce the number of workers:
```python
grader.set_other_options(build_only=True, parallel_workers=10)
```

### Build Errors
Check the log file path shown in the `[FAIL]` line for details:
```bash
cat /tmp/ygrader_jsmith_abc123.log
```

### Students Already Graded
Students with existing grades are skipped (`[SKIP]`). To re-build:
1. Delete their entry from the deductions YAML file, or
2. Use the `[u]` undo feature during normal grading

### Cleanup
Temporary log files accumulate in `/tmp`. Clean them periodically:
```bash
rm /tmp/ygrader_*.log
```
