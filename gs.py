import os
import argparse
import json
import subprocess
import time
import tempfile

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


def get_pr_url():
    command = "sl log -r . --template '{github_pull_request_url}'"
    return shell_out(command) 

def add_reviewer(reviewer, pr_url):
    command = f"gh pr edit {pr_url} --add-reviewer {reviewer}"
    return shell_out(command)

def add_label(label, pr_url):
    command = f"gh pr edit {pr_url} --add-label {label}"
    return shell_out(command)

def edit_pr(args):
    reviewers = args.reviewers
    labels = args.labels
    reviewer_teams = args.reviewer_teams
    pr_url = get_pr_url()
    label_string = ""
    reviewer_string = ""
    for team in reviewer_teams:
        reviewers.append(f"databricks/{team}")

    if labels:
        label_string = f"--add-label {','.join(labels)}"
    if reviewers:
        reviewer_string = f"--add-reviewer {','.join(reviewers)}"

    command = f"gh pr edit {pr_url} {label_string} {reviewer_string}"

    if reviewer_teams:
        for team in reviewer_teams:
            add_reviewer(f"databricks/{team}", pr_url)
    return shell_out(command)
    
def comment_jenkins_merge(pr_url):
    command = f"gh pr comment {pr_url} -b 'jenkins merge'"
    return shell_out(command)

def is_master():
   ret = shell_out("sl phase")
   _, phase = ret.split(" ")
   return phase == "public"

def update_pr():
    command = '''sl log -r . --template '{github_pull_request_url}' | xargs -I@ gh pr view @ --json headRefName | jq .headRefName | xargs -I@ sl push --to "b/@" -f'''
    print("Updated PR")
    return shell_out(command)


def update_stack(args):
    current_commit = shell_out("sl log -r . --template '{node}'")
    while not is_master():
        update_pr()
        shell_out("sl prev")

    shell_out(f"sl goto {current_commit}")

def is_merged(pr_url):
    command = f"gh pr view {pr_url} --json state"
    ret = json.loads(shell_out(command))
    return "state" in ret and ret["state"] == "MERGED"


def merge_stack(args):
    num_prs = args.num_prs
    while num_prs > 0:
        pr_url = get_pr_url()
        if not pr_url:
            print(f"Commit has no PR URL. Exiting!")
            return

        add_label("automerge,autoformat", pr_url)
        while not is_merged(pr_url):
            # TODO: Automatically abort or rebase it we fail any tests.
            # TODO: Do we ever need to jenkins merge?
            print(f"{pr_url} is still not merged. Check for any failures in mergability.")
            time.sleep(60)
        
        shell_out("sl next")
        shell_out("sl pull && sl rebase -d remote/master")
        update_pr()

        num_prs -= 1

def edit_body(args):
    # TODO: Also persist in the commit body?
    editor = os.environ.get('EDITOR')
    if not editor:
        return ("No EDITOR found in environment.")

    pr_url = get_pr_url()
    current_pr_body = shell_out(f"gh pr view {pr_url} --json body")
    current_pr_body = json.loads(current_pr_body)["body"]

    is_stacked = False
    if "---" in current_pr_body:
        is_stacked = True
        stack_navigation_section = current_pr_body.split('---')[1].strip()
        stack_navigation_section = "---\n" + stack_navigation_section
    else:
        stack_navigation_section = ""

    current_pr_description = shell_out("sl log -r . --template '{desc}'")

    default_template = f"""## What changes are proposed in this pull request?
{"Note that this PR is stacked: only review the top commit" if is_stacked else ""}

## How is this tested?


{stack_navigation_section}
"""

    # populate temporary file with default template
    _, filename = tempfile.mkstemp(text=True)
    with open(filename, 'w') as f:
        f.write(default_template)

    cmd = '%s %s' % (editor, filename)
    write_status = subprocess.call(cmd, shell=True)

    if write_status != 0:
        os.remove(filename)
        raise Exception("Editor exited unhappily.")
    
    with open(filename) as f:
        if f.read() == default_template:
            print("No changeswere made, exiting without editing the PR.")
            return
    shell_out(f"gh pr edit {pr_url} --body-file {filename}")

    # TODO: Rethink this. Something like jf sync, perhaps?
    # shell_out(f"sl metaedit -l {filename}")


def review(args):
    edit_body(args)
    pr_url = get_pr_url()
    add_reviewer("databricks/eng-kubernetes-runtime-team", pr_url)
    add_reviewer("databricks/eng-kubernetes-runtime-team", pr_url)

def sync(args):
    # TODO: Implement syncing a whole stack at once.
    pr_url = get_pr_url()
    title_and_body = json.loads(shell_out(f"gh pr view {pr_url} --json title,body"))
    _, filename = tempfile.mkstemp(text=True)
    with open(filename, 'w') as f:
        f.write(title_and_body["title"])
        f.write("\n")
        f.write(title_and_body["body"])
    
    shell_out(f"sl metaedit -l {filename}")


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='commands', dest='command')


    jenkins_merge_parser = subparsers.add_parser('jenkinsmerge', help='Jenkins merge command')
    jenkins_merge_parser.set_defaults(func=comment_jenkins_merge)

    edit_parser = subparsers.add_parser('edit', help='Edit reviewers and labels')
    edit_parser.add_argument('--reviewers', nargs='+', help='Reviewers to add', default=[])
    edit_parser.add_argument('--reviewer-teams', nargs='+', help='Reviewer teams to add', default=[])
    edit_parser.add_argument('--labels', nargs='+', help='Labels to add', default=[])
    edit_parser.set_defaults(func=edit_pr)

    update_stack_parser = subparsers.add_parser('updatestack', help='Updates the PRs. Must have been submitted with sapling.')
    update_stack_parser.set_defaults(func=update_stack)

    merge_stack_parser = subparsers.add_parser('mergestack', help='Merges the stack. Continues to wait.')
    merge_stack_parser.add_argument('--num_prs', type=int, help='Number of PRs to merge')
    merge_stack_parser.set_defaults(func=merge_stack)

    add_body_parser = subparsers.add_parser('editbody', help='adds a body in the correct format to the current PR.')
    add_body_parser.set_defaults(func=edit_body)

    review_parser = subparsers.add_parser("review", help="Prepares a PR for review.")
    review_parser.set_defaults(func=review)

    sync_parser = subparsers.add_parser("sync", help="Syncs local commit description with github")
    sync_parser.set_defaults(func=sync)


    args = parser.parse_args()

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()



if __name__ == "__main__":
    main()
