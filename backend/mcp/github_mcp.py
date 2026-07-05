import os
import base64
from github import Github
from github.GithubException import GithubException
from dotenv import load_dotenv

load_dotenv()

class GitHubMCP:
    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("❌ Missing environment variable: GITHUB_TOKEN")
        self.github = Github(token)   

    def get_pr_files(self, repo_name: str, pr_number: int, max_files: int = 5) -> list:
        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            ref_branch = pr.head.sha
            files = []
            files_processed = 0

            for f in pr.get_files():
                if files_processed >= max_files:
                    break
                if f.status == "removed" or not f.filename:
                    continue

                full_code = ""
                try:
                    contents = repo.get_contents(f.filename, ref=ref_branch)
                    if contents.encoding == "base64":
                        full_code = base64.b64decode(contents.content).decode("utf-8")
                    else:
                        full_code = contents.decoded_content.decode("utf-8")
                except Exception as file_err:
                    print(f"⚠️ Could not pull full text for {f.filename}, falling back to patch. Error: {file_err}")
                    full_code = f.patch or ""

                files.append({
                    "filename": f.filename,
                    "code": full_code,
                    "patch": f.patch or "",
                    "additions": f.additions,
                    "deletions": f.deletions
                })
                files_processed += 1

            return files

        except GithubException as ge:
            print(f"❌ GitHub API Error fetching PR #{pr_number}: {ge.data.get('message', ge)}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error fetching PR #{pr_number}: {e}")
            return []

    def post_comment(self, repo_name: str, pr_number: int, comment: str):
        """Post DevPilot review as a comment directly on the PR"""
        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            print(f"✅ Review comment posted on PR #{pr_number}")
        except GithubException as ge:
            print(f"❌ Failed to post PR comment: {ge}")

    def create_security_issue(self, repo_name: str, title: str, body: str):
        """Create a GitHub issue for critical security vulnerabilities"""
        try:
            repo = self.github.get_repo(repo_name)
            repo.create_issue(
                title=f"🔐 Security: {title}",
                body=body,
                labels=["security", "devpilot-ai"]
            )
            print(f"✅ Security issue created: {title}")
        except GithubException as ge:
            print(f"❌ Failed to create security issue: {ge}")

    def get_pr_files_since(self, repo_name: str, pr_number: int, since_sha: str, max_files: int = 5) -> list:
        """Fetches only files changed since a previous commit SHA. Falls back to
        the full file list if the comparison fails (e.g. force-push rewrote history)."""
        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            head_sha = pr.head.sha

            if since_sha == head_sha:
                return []  # nothing new since last review

            comparison = repo.compare(since_sha, head_sha)
            ref_branch = head_sha
            files = []
            files_processed = 0

            for f in comparison.files:
                if files_processed >= max_files:
                    break
                if f.status == "removed" or not f.filename:
                    continue

                full_code = ""
                try:
                    contents = repo.get_contents(f.filename, ref=ref_branch)
                    if contents.encoding == "base64":
                        full_code = base64.b64decode(contents.content).decode("utf-8")
                    else:
                        full_code = contents.decoded_content.decode("utf-8")
                except Exception:
                    full_code = f.patch or ""

                files.append({
                    "filename": f.filename, "code": full_code, "patch": f.patch or "",
                    "additions": f.additions, "deletions": f.deletions
                })
                files_processed += 1

            return files

        except Exception as e:
            print(f"⚠️ Incremental diff failed, falling back to full file list: {e}")
            return self.get_pr_files(repo_name, pr_number, max_files=max_files)



# Local Test verification
if __name__ == "__main__":
    try:
        mcp = GitHubMCP()
        user = mcp.github.get_user()
        print(f"✅ GitHub connected successfully as: {user.login}")
    except Exception as e:
        print(f"❌ Connection testing failed: {e}")
