# TODO:
# 1. Update stack
# 2. Add reviewers to stack 
# 3. Add labels to stack.
# 4. Comment jenkins merge on stack.

# 5. Merge stacked PR. In the background, monitor the base PR if it's merged, and then if it is, then pull && rebase.
import argparse
import json
import subprocess
import time

def shell_out(command):
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


    args = parser.parse_args()

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()



if __name__ == "__main__":
    main()
