
import argparse
import subprocess
import sys
import tempfile

DEVBOX_URL = "devbox.databricks.com"

ALIASES = {
    "buck": "bazel",
    "kubecfg" : "~/universe/bin/kubecfg"
}

def shell_out(command):
    print(f"Running command: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        stdout = result.stdout.strip()
        # TODO: Comment this out whenever ready.
        print(stdout)
        print(result.stderr.strip())
        return stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        raise e

def remote_shell_out(command):
    remote_shell_cmd = f"ssh -t {DEVBOX_URL} 'cd ~/universe && {command}'"
    print(f"command: {remote_shell_cmd}")
    return subprocess.run(remote_shell_cmd, shell=True, check=True)

def get_current_base():
    return shell_out("sl log -r 'last(public() and ancestors(.))' --template '{node}'")

def clear_remote_state(base_commit):
    reset_cmd = f"git reset --hard {base_commit} && git clean -f -d"
    try:
        remote_shell_out(reset_cmd)
    except Exception as e:
        # Try again after fetching.
        remote_shell_out(f"git fetch origin master")
        remote_shell_out(reset_cmd)

def is_curr_dirty():
    res = shell_out("sl status")
    return bool(res)

# Syncs the local directory.
# Does NOT include dirty files. TODO: Add a log message to indicate this cleanly.
def sync(args, unknown_flags):
    if is_curr_dirty():
        print("[WARNING] Current directory is dirty. Those changes will NOT be synced.")

    clear_remote_state(get_current_base())
    with tempfile.NamedTemporaryFile() as temp_file:
        cmd = f"sl export -r 'ancestors(.) and not public()' -o {temp_file.name}"
        shell_out(cmd)
        cmd = f"scp {temp_file.name} devbox.databricks.com:/tmp/patchset.patch"
        shell_out(cmd)

        cmd = f"git apply /tmp/patchset.patch"
        remote_shell_out(cmd)

    print("Successfully synced devserver with current dir")

def run(args, unknown_flags):
    command = " ".join([ALIASES[cmd] if cmd in ALIASES else cmd for cmd in sys.argv[2:]])
    remote_shell_out(command)

def run_last(args, unknown_flags):
    last_command = shell_out("fc -ln -1")
    print(f"Rerunning last command remotely: {last_command}")

def auth(args, unknown_flags):
    pass


def main():
    parser = argparse.ArgumentParser(description="devserver scripts")
    subparsers = parser.add_subparsers()

    sync_parser = subparsers.add_parser("sync", help="Syncs the remote server's universe repo with the current repo's")
    sync_parser.set_defaults(func=sync)

    run_parser = subparsers.add_parser("run", help="Run a command on the remote server.")
    run_parser.add_argument("cmd", nargs='+', help="The command to execute on the remote server.")
    run_parser.set_defaults(func=run)

    run_last_parser = subparsers.add_parser("runlast", help="Run a command on the remote server.")
    run_last_parser.set_defaults(func=run_last)

    auth_parser = subparsers.add_parser("auth", help="Authenticate for specific services.")
    auth_parser.add_argument("what", choices=["kube"], help="What to login to")
    run_last_parser.set_defaults(func=auth)


    args, unknown = parser.parse_known_args()
    if hasattr(args, "func"):
        args.func(args, unknown)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
