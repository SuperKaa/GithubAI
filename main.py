import ollama, re, subprocess, os, shutil
from pathlib import Path
from colorama import init, Fore

init(autoreset=True)
ENV_FILE = Path(".env")
ALLOWED = [
    "git init","git status","git add","git commit","git branch",
    "git checkout","git switch","git remote","git push","git pull",
    "git log","gh repo create","gh auth login"
]

# --------- Environment ---------
def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line: k,v=line.split("=",1); env[k]=v
    return env

def save_env(env):
    ENV_FILE.write_text("\n".join(f"{k}={v}" for k,v in env.items()))

def setup_env():
    env = load_env()
    if "GIT_USERNAME" not in env or "GIT_EMAIL" not in env:
        env["GIT_USERNAME"]=input(Fore.YELLOW+"Git username: ").strip()
        env["GIT_EMAIL"]=input(Fore.YELLOW+"Git email: ").strip()
    os.system(f'git config --global user.name "{env["GIT_USERNAME"]}"')
    os.system(f'git config --global user.email "{env["GIT_EMAIL"]}"')
    save_env(env)
    return env

# --------- Git helpers ---------
def run(cmd):
    print(Fore.GREEN+f"$ {cmd}")
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.stdout.strip(): print(p.stdout.strip())
    if p.stderr.strip(): print(Fore.RED+p.stderr.strip())

def repo_state():
    is_repo = Path(".git").exists()
    branch = "main"
    if is_repo:
        try:
            branch = subprocess.check_output(
                "git rev-parse --abbrev-ref HEAD", shell=True, text=True).strip()
        except: pass
    origin = ""
    try:
        origin = subprocess.check_output(
            "git remote get-url origin", shell=True, text=True).strip()
    except: pass
    gh_available = shutil.which("gh") is not None
    status = subprocess.run("git status --porcelain", shell=True,
                            capture_output=True, text=True).stdout.strip()
    dirty = bool(status)
    return is_repo, branch, bool(origin), origin, gh_available, dirty

def commit_changes():
    run("git add .")
    run('git commit -m "Initial commit"')

# --------- AI parsing ---------
def parse(text):
    # Always capture everything between < > for AI commands
    return re.findall(r"<(.*?)>", text, re.DOTALL)

def ask_ai(user):
    sys_prompt = """
You are a git assistant for beginners. Always follow this workflow automatically:

1. Initialize repo if missing: <git init>
2. Stage all changes: <git add .>
3. Commit all changes: <git commit -m "Initial commit">
4. If no remote origin and gh CLI exists, create GitHub repo automatically:
   <gh repo create <repo_name> --source=. --push>
   Use the repo name from the user's sentence.
5. Push current branch to origin: <git push -u origin <branch>>

Rules:
- Only output commands wrapped in < >. No explanations.
- Multiple commands → multiple < > lines.
- Use the actual branch name.
"""
    resp = ollama.chat(model="qwen:4b", messages=[
        {"role":"system","content":sys_prompt},
        {"role":"user","content":user}
    ])
    return resp["message"]["content"]

# --------- Main workflow ---------
def main():
    env = setup_env()
    while True:
        q = input(Fore.CYAN+"> ").strip()
        if q.lower() in {"exit","quit"}: break

        # 1. Initialize repo if missing
        is_repo, branch, has_origin, origin_url, gh_available, dirty = repo_state()
        if not is_repo:
            run("git init")
            is_repo = True

        # 2. Commit changes if dirty
        if dirty:
            commit_changes()

        # 3. Run all AI commands first (including gh repo create)
        ai_cmds = parse(ask_ai(q))
        for c in ai_cmds:
            run(c.strip())

        # 4. Re-check repo state after AI commands
        is_repo, branch, has_origin, origin_url, gh_available, dirty = repo_state()

        # 5. Only ask for manual URL if gh CLI missing and origin still not set
        if not has_origin and not gh_available:
            url = input(Fore.YELLOW+"Enter GitHub remote URL: ").strip()
            run(f"git remote add origin {url}")

        # 6. Push current branch
        run(f"git push -u origin {branch}")

if __name__=="__main__": main()
