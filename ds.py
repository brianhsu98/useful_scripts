
import argparse
import subprocess
import sys
import tempfile

DEVBOX_URL = "devbox.databricks.com"

ALIASES = {
    "buck": "bazel",
    "kubecfg" : "bin/kubecfg"
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
    # No idea why bash profile isn't working
    remote_shell_cmd = f"ssh -t {DEVBOX_URL} ' export PATH=$HOME/universe/bin:$PATH; export HCVAULT_DEFAULT_CLI_ROLE=eng-kubernetes-runtime-team; cd ~/universe && {command}'"
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
    cmds = sys.argv[2:]
    to_join = []
    for cmd in cmds:
        # handles the case where there is a string inside the cmd (for example, if we want to do an && on the remote.)
        cmd = [ALIASES[cmd] if cmd in ALIASES else cmd for cmd in cmd.split()]
        to_join.extend(cmd)
    
    command = " ".join(to_join)
    remote_shell_out(command)

def run_interactive(args, unknown_flags):
    selected_command = subprocess.run("fc -ln 0 | sort | uniq | fzf", shell=True, capture_output=True)
    print("selected_command")

def auth(args, unknown_flags):
    base = "ssh -t -L 8771:127.0.0.1:8771 devbox.databricks.com 'cd universe && {auth_cmd}'"

    if args.what == "kube":
        auth_cmd = f"bin/tshx --env={args.env} kube-login --all --as=cluster-admin"
    elif args.what == "harbor-dp":
        auth_cmd = f"eng-tools/bin/get-harbor-dp-access {args.env}"
        pass
    elif args.what == "harbor":
        auth_cmd = f"eng-tools/bin/get-harbor-access {args.env}"
    else:
        print("Unknown arg")

    return subprocess.run(base.format(auth_cmd=auth_cmd), shell=True, check=True)


def main():
    parser = argparse.ArgumentParser(description="devserver scripts")
    subparsers = parser.add_subparsers()

    sync_parser = subparsers.add_parser("sync", help="Syncs the remote server's universe repo with the current repo's")
    sync_parser.set_defaults(func=sync)

    run_parser = subparsers.add_parser("run", help="Run a command on the remote server.")
    run_parser.add_argument("cmd", help="The command to execute on the remote server.")
    run_parser.set_defaults(func=run)

    auth_parser = subparsers.add_parser("auth", help="Authenticate for specific services.")
    auth_parser.add_argument("what", help="What to login to")
    auth_parser.add_argument('--env', choices=['dev', 'staging', 'prod'], help='Environment: dev, staging, or prod.', default='dev')
    auth_parser.set_defaults(func=auth)

    run_interactive_parser = subparsers.add_parser("ri")
    run_interactive_parser.set_defaults(func=run_interactive)

    # Default to run.
    parser.set_defaults(func=run)

    args, unknown = parser.parse_known_args()
    args.func(args, unknown)

if __name__ == '__main__':
    main()
