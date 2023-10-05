
import argparse
import subprocess
import tempfile

DEVBOX_URL = "devbox.databricks.com"

ALIASES = {
    "buck": "bazel"
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
    remote_shell_cmd = f"ssh {DEVBOX_URL} 'cd universe && {command}'"
    return shell_out(remote_shell_cmd)

def get_current_base():
    return shell_out("sl log -r 'last(public() and ancestors(.))' --template '{node}'")

def clear_remote_state(base_commit):
    remote_shell_out(f"git reset --hard {base_commit}")

# Syncs the local directory.
# Does NOT include dirty files. TODO: Add a log message to indicate this cleanly.
def sync(args):
    with tempfile.NamedTemporaryFile() as temp_file:
        cmd = f"sl export -r 'ancestors(.) and not public()' -o {temp_file.name}"
        shell_out(cmd)
        cmd = f"scp {temp_file.name} devbox.databricks.com:/tmp/patchset.patch"
        shell_out(cmd)

        cmd = f"git apply /tmp/patchset.patch"
        remote_shell_out(cmd)


def run(args):
    command = " ".join([ALIASES[cmd] if cmd in ALIASES else cmd for cmd in args.cmd])
    remote_shell_cmd = f"ssh {DEVBOX_URL} 'cd universe && {command}'"
    subprocess.call(remote_shell_cmd, shell=True)


def main():
    parser = argparse.ArgumentParser(description="devserver scripts")
    subparsers = parser.add_subparsers()

    sync_parser = subparsers.add_parser("sync", help="Syncs the remote server's universe repo with the current repo's")
    sync_parser.set_defaults(func=sync)

    run_parser = subparsers.add_parser("run", help="Run a command on the remote server.")
    run_parser.add_argument("cmd", nargs='+', help="The command to execute on the remote server.")
    run_parser.set_defaults(func=run)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
