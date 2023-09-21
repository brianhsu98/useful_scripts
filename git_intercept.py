import subprocess
import sys


ORIGINAL_GIT = "/usr/bin/git"
SAPLING = "/opt/homebrew/bin/sl"

GIT_TO_SAPLING_COMMAND_MAPPING = {
    "rev-parse --show-toplevel": "root",
    "rev-parse --short=7 HEAD": "id -i",
    "rev-parse HEAD": "id -i",
    "rev-parse --abbrev-ref HEAD": "bookmark",
    "version": "version",
    "config user.email": "config ui.username",
    
}

def is_git_dir():
    try:
        subprocess.check_output([ORIGINAL_GIT, "rev-parse", "--git-dir"], shell=True)
    except subprocess.CalledProcessError as e:
        return False
    return True

def run_command(command):
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        output = e.output
    print(output.decode())


def run_git(args):
    command = " ".join([ORIGINAL_GIT] + args)
    run_command(command)

def run_sapling(args):
    command = " ".join([SAPLING] + args)
    run_command(command)


def main():
    args = sys.argv[1:]
    if is_git_dir():
        run_git(args)
    else:
        run_git(args)


if __name__ == "__main__":
    main()