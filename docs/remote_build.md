# Remote Build

The remote build feature allows you to run build commands on a remote machine via SSH. This is useful when:

- The build requires software not installed locally (e.g., Vivado for FPGA synthesis)
- The build is resource-intensive and you want to offload it to a server
- You need to run builds on a specific machine with licensed software

## Basic Usage

Import the `run_remote_build` function from ygrader:

```python
from ygrader import run_remote_build, RemoteBuildError
```

Then call it in your grading callback:

```python
def grading_handler(lab_name, student_code_path, repo_url, tag, **kwargs):
    run_remote_build(
        remote_host="server.example.com",
        remote_work_path="/tmp/grading",
        repo_url=repo_url,
        tag=tag,
        commands=[
            ("lab_tools/adder", ["make", "sim"]),
        ],
        files_to_copy=["lab_tools/adder/output.txt"],
        student_code_path=student_code_path,
    )
```

## How It Works

The `run_remote_build` function performs these steps:

1. **SSH Connection Test**: Verifies SSH connectivity to the remote host
2. **Clone Repository**: Clones the student's repo at the specified tag on the remote machine
3. **Run Commands**: Executes each command in sequence from the specified directory
4. **Copy Files Back**: Uses SCP to copy specified output files back to the local machine
5. **Cleanup**: Removes the remote clone (unless `cleanup=False`)

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `remote_host` | str | SSH hostname (e.g., `"server.example.com"` or `"user@server"`) |
| `remote_work_path` | str | Base path on remote machine for cloning (e.g., `"/tmp/grading"`) |
| `repo_url` | str | Git repository URL to clone |
| `tag` | str | Git tag or branch to checkout |
| `commands` | List[Tuple[str, List[str]]] | List of (relative_path, command_list) tuples |
| `files_to_copy` | List[str] | File paths relative to repo root to copy back |
| `student_code_path` | Path | Local directory to copy files into |
| `cleanup` | bool | Delete remote clone after completion (default: `True`) |
| `use_username_subdir` | bool | Create username subdirectory under work path (default: `True`) |
| `env_setup` | str | Shell command(s) to run before each command (e.g., `"source settings.sh"`) |
| `output` | TextIO | File object for output (default: `sys.stdout`) |

## Example: FPGA Synthesis with Vivado

```python
def grading_handler(lab_name, student_code_path, repo_url, tag, output=None, **kwargs):
    print("Running remote build for FPGA synthesis...", file=output)
    
    run_remote_build(
        remote_host="fpga-server.example.com",
        remote_work_path="/nvme/grading",
        repo_url=repo_url,
        tag=tag,
        commands=[
            ("lab_tools/logic_functions", ["make", "implement"]),
        ],
        files_to_copy=["lab_tools/logic_functions/work"],
        student_code_path=student_code_path,
        env_setup="source /tools/Xilinx/Vivado/2024.1/settings64.sh",
        output=output,
    )
```

## SSH Configuration

The remote build uses SSH with these options:

- **BatchMode**: Fails if password is required (use SSH keys)
- **StrictHostKeyChecking=accept-new**: Automatically accepts new host keys
- **ConnectTimeout=10**: 10 second connection timeout
- **X11 forwarding disabled**: Prevents X11 errors

### Setting Up SSH Keys

Ensure you have passwordless SSH access to the remote host:

```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519

# Copy public key to remote server
ssh-copy-id user@server.example.com

# Test connection
ssh user@server.example.com echo "Connected!"
```

## Error Handling

The function raises `RemoteBuildError` on failure:

```python
from ygrader import run_remote_build, RemoteBuildError

try:
    run_remote_build(...)
except RemoteBuildError as e:
    print(f"Remote build failed: {e}")
    # e.command_output contains the command's stdout/stderr
```

## Username Subdirectory

By default, `use_username_subdir=True` creates a subdirectory named after the SSH user under `remote_work_path`. This prevents conflicts when multiple TAs grade simultaneously:

```
/tmp/grading/
├── ta1/
│   └── student-repo/
└── ta2/
    └── student-repo/
```

Set `use_username_subdir=False` to clone directly in `remote_work_path`.

## Output Logging

All SSH and SCP commands are logged with prefixes:
- `[SSH]` - Remote commands
- `[SCP]` - File copy operations

When using parallel build mode, output goes to per-student log files automatically.
