import os
import subprocess
import sys
import urllib.parse


def clone_repo(repo_name: str, username: str, password: str, target_dir: str = None, use_ssh: bool = True):
    if use_ssh:
        repo_url = f"git@github.com-ssh443:{username}/{repo_name}.git"
    else:
        encoded_username = urllib.parse.quote(username, safe="")
        encoded_password = urllib.parse.quote(password, safe="")
        repo_url = f"https://{encoded_username}:{encoded_password}@github.com/{username}/{repo_name}.git"

    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, repo_name)
    if os.path.exists(target_path):
        print(f"Destination directory {target_path} already exists, skipping clone")
        return False

    command = [
        "git", "clone",
        "--branch", "main",
        repo_url,
        os.path.join(target_dir, repo_name)
    ]

    try:
        result = subprocess.run(
            command,
            cwd=target_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        print(f"Successfully cloned {repo_name} to {target_dir}")
        print("STDOUT:", result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone {repo_name}")
        print("STDERR:", e.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("Clone operation timed out")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python clone_repo.py <repo_name>")
        sys.exit(1)

    repo_name = sys.argv[1]
    username = "REDACTED_USERNAME"
    password = "REDACTED_PASSWORD"

    clone_repo(repo_name, username, password)