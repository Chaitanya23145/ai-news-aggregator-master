import os
import json

# 🔧 CHANGE THIS
OLD_NAME = "ai-news-aggregator"
NEW_NAME = "your-new-project-name"

OPENAI_API_KEY = "your_openai_api_key_here"


IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".idea"}
IGNORE_FILES = {"setup_project.py", ".env", "combined_code.txt"}


def is_text_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            f.read(1000)
        return True
    except:
        return False


def replace_in_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        updated = content.replace(OLD_NAME, NEW_NAME)

        if updated != content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(updated)

            print(f"✅ Updated: {filepath}")

    except Exception as e:
        print(f"❌ Skipped: {filepath}")


def walk_and_replace(root):
    for foldername, subfolders, filenames in os.walk(root):
        subfolders[:] = [d for d in subfolders if d not in IGNORE_DIRS]

        for filename in filenames:
            if filename in IGNORE_FILES:
                continue

            filepath = os.path.join(foldername, filename)

            if is_text_file(filepath):
                replace_in_file(filepath)


def create_env():
    env_content = f"""# Environment Variables

OPENAI_API_KEY={OPENAI_API_KEY}

# App Config
APP_NAME={NEW_NAME}
ENV=development

# Database (optional - edit if needed)
DATABASE_URL=postgresql://user:password@localhost:5432/{NEW_NAME}

# News Config
DEFAULT_HOURS=24
TOP_NEWS_LIMIT=10
"""

    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)

    print("✅ .env created")


def update_pyproject():
    if os.path.exists("pyproject.toml"):
        try:
            with open("pyproject.toml", "r", encoding="utf-8") as f:
                content = f.read()

            content = content.replace(OLD_NAME, NEW_NAME)

            with open("pyproject.toml", "w", encoding="utf-8") as f:
                f.write(content)

            print("✅ pyproject.toml updated")

        except:
            print("⚠️ pyproject update failed")


def update_workspace():
    for file in os.listdir():
        if file.endswith(".code-workspace"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                content = content.replace(OLD_NAME, NEW_NAME)

                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)

                print(f"✅ workspace updated: {file}")
            except:
                pass


if __name__ == "__main__":
    print("\n🚀 Setting up project...\n")

    root_dir = os.getcwd()

    walk_and_replace(root_dir)
    create_env()
    update_pyproject()
    update_workspace()

    print("\n🔥 DONE! Project renamed + env ready\n")
