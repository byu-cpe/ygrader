"""Module for running builds on remote machines via SSH."""

import pathlib
import subprocess
import sys
from typing import List, Optional, TextIO, Tuple


class RemoteBuildError(Exception):
    """Exception raised when a remote build operation fails."""

    def __init__(self, message: str, command_output: str = ""):
        self.message = message
        self.command_output = command_output
        super().__init__(self.message)

    def __str__(self):
        if self.command_output:
            return f"{self.message}\n\nCommand output:\n{self.command_output}"
        return self.message


def run_remote_build(  # pylint: disable=too-many-positional-arguments
    remote_host: str,
    remote_work_path: str,
    repo_url: str,
    tag: str,
    commands: List[Tuple[str, List[str]]],
    files_to_copy: List[str],
    student_code_path: pathlib.Path,
    cleanup: bool = True,
    use_username_subdir: bool = True,
    env_setup: str = "",
    output: Optional[TextIO] = None,
) -> List[str]:
    """Run a build on a remote machine and copy files back.

    This function:
    1. Connects to the remote host via SSH
    2. Clones the student repo at the specified tag
    3. Runs the provided commands in sequence
    4. Copies the specified files back to the local machine
    5. Optionally cleans up the remote clone

    Args:
        remote_host: SSH hostname (e.g., "server.example.com" or "user@server")
        remote_work_path: Base path on remote machine where repo will be cloned
            (e.g., "/tmp/grading"). By default, a subdirectory named after the
            remote username will be created under this path.
        repo_url: Git repository URL to clone
        tag: Git tag to checkout after cloning
        commands: List of (relative_path, command_list) tuples. Each command
            will be run from the specified path relative to the repo root.
            Example: [("lab_tools/adder", ["make", "sim"])]
        files_to_copy: List of file paths relative to repo root to copy back
        student_code_path: Local student code directory to copy files into
        cleanup: If True (default), delete the remote clone after completion
        use_username_subdir: If True (default), create a subdirectory under
            remote_work_path named after the remote user's username. This helps
            avoid conflicts when multiple users share the same work path.
        env_setup: Optional shell command(s) to run before each command to set up
            the environment (e.g., "source /path/to/settings.sh"). This is prepended
            to each command with "&&".
        output: Optional file object to write command output to. If None, uses
            sys.stdout.

    Returns:
        List of command output strings (stdout + stderr combined) for each command

    Raises:
        RemoteBuildError: If SSH connection fails, clone fails, any command fails,
            or file copy fails
    """
    if output is None:
        output = sys.stdout

    # Extract repo name from URL for the clone directory
    # Handle both https://github.com/org/repo.git and git@github.com:org/repo.git
    repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
    if ":" in repo_name:
        repo_name = repo_name.split(":")[-1].split("/")[-1]

    command_outputs = []
    remote_repo_path = None  # Initialize to None for cleanup check

    try:
        # Test SSH connection and get username if needed
        _run_ssh_command(remote_host, ["echo", "SSH connection successful"])

        # Determine the actual work path (with optional username subdirectory)
        if use_username_subdir:
            username = _run_ssh_command(remote_host, ["whoami"]).strip()
            actual_work_path = f"{remote_work_path}/{username}"
        else:
            actual_work_path = remote_work_path

        remote_repo_path = f"{actual_work_path}/{repo_name}"

        # Create work directory and clone repo
        clone_commands = [
            f"mkdir -p {actual_work_path}",
            f"rm -rf {remote_repo_path}",  # Clean any previous clone
            f"git clone --depth 1 --branch {tag} {repo_url} {remote_repo_path}",
        ]
        for cmd in clone_commands:
            print(f"[SSH] {cmd}", file=output)
            cmd_output = _run_ssh_command(remote_host, [cmd])
            if cmd_output.strip():
                print(cmd_output, file=output)

        # Run each command in sequence
        for relative_path, cmd_list in commands:
            work_dir = (
                f"{remote_repo_path}/{relative_path}"
                if relative_path
                else remote_repo_path
            )
            # Build the full command with cd and optional env setup
            cmd_str = " ".join(cmd_list)
            if env_setup:
                full_cmd = f"{env_setup} && cd {work_dir} && {cmd_str}"
            else:
                full_cmd = f"cd {work_dir} && {cmd_str}"
            print(f"[SSH] cd {work_dir} && {cmd_str}", file=output)
            cmd_output = _run_ssh_command(remote_host, [full_cmd])
            if cmd_output.strip():
                print(cmd_output, file=output)
            command_outputs.append(cmd_output)

        # Copy files back using scp
        for file_path in files_to_copy:
            remote_file = f"{remote_repo_path}/{file_path}"
            local_file = student_code_path / file_path

            # Create local directory if needed
            local_file.parent.mkdir(parents=True, exist_ok=True)

            print(f"[SCP] {remote_file} -> {local_file}", file=output)
            _run_scp_command(remote_host, remote_file, local_file)

    finally:
        # Cleanup remote directory if requested
        if cleanup and remote_repo_path is not None:
            try:
                _run_ssh_command(remote_host, [f"rm -rf {remote_repo_path}"])
            except RemoteBuildError:
                pass  # Ignore cleanup errors

    return command_outputs


def _run_ssh_command(remote_host: str, command: List[str]) -> str:
    """Run a command on the remote host via SSH.

    Args:
        remote_host: SSH hostname
        command: Command and arguments to run

    Returns:
        Combined stdout and stderr output

    Raises:
        RemoteBuildError: If the SSH command fails
    """
    ssh_cmd = [
        "ssh",
        "-x",  # Disable X11 forwarding
        "-o",
        "BatchMode=yes",  # Fail if password is required
        "-o",
        "StrictHostKeyChecking=accept-new",  # Accept new host keys
        "-o",
        "ConnectTimeout=10",
        remote_host,
    ] + command

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,  # 5 minute timeout per command
        )
    except subprocess.TimeoutExpired as e:
        raise RemoteBuildError(
            f"SSH command timed out: {' '.join(command)}",
            e.stdout or "",
        ) from e
    except FileNotFoundError as e:
        raise RemoteBuildError(
            "SSH client not found. Is OpenSSH installed?",
        ) from e

    output = result.stdout + result.stderr

    if result.returncode != 0:
        raise RemoteBuildError(
            f"SSH command failed with exit code {result.returncode}: {' '.join(command)}",
            output,
        )

    return output


def _run_scp_command(
    remote_host: str, remote_path: str, local_path: pathlib.Path
) -> None:
    """Copy a file or directory from the remote host via SCP.

    Args:
        remote_host: SSH hostname
        remote_path: Path to file or directory on remote host
        local_path: Local path to copy to

    Raises:
        RemoteBuildError: If the SCP command fails
    """
    scp_cmd = [
        "scp",
        "-r",  # Recursive copy (works for both files and directories)
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ForwardX11=no",
        f"{remote_host}:{remote_path}",
        str(local_path),
    ]

    try:
        result = subprocess.run(
            scp_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,  # 5 minute timeout for potentially large directory copies
        )
    except subprocess.TimeoutExpired as e:
        raise RemoteBuildError(
            f"SCP timed out copying: {remote_path}",
            e.stdout or "",
        ) from e
    except FileNotFoundError as e:
        raise RemoteBuildError(
            "SCP client not found. Is OpenSSH installed?",
        ) from e

    if result.returncode != 0:
        output = result.stdout + result.stderr
        raise RemoteBuildError(
            f"Failed to copy: {remote_path}",
            output,
        )
