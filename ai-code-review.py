import os
import yaml
import gitlab
import google.generativeai as genai
import openai
import argparse
from dotenv import load_dotenv

load_dotenv()

GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_PRIVATE_TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PROJECT_ID = os.getenv("CI_PROJECT_ID")

def load_system_instruction(file_path=".ai-code-review.yml"):
    default_system_instruction = "You are a senior developer reviewing code changes from a commit or merge request. Your role is to provide a detailed code review."
    default_prompt_instruction = "Review the git diff of a recent commit, focusing on clarity, structure, and security."

    project_path = os.getenv("CI_PROJECT_DIR")
    if not project_path:
        print("Warning: CI_PROJECT_DIR environment variable not found. Using default instructions.")
        return default_system_instruction, default_prompt_instruction

    absolute_file_path = os.path.join(project_path, file_path)

    try:
        with open(absolute_file_path, 'r') as file:
            data = yaml.safe_load(file)
            if data is None:
                print(f"Warning: {file_path} is empty. Using default instructions.")
                return default_system_instruction, default_prompt_instruction
            system_instruction = data.get("system_instruction", default_system_instruction)
            prompt_instruction = data.get("prompt_instruction", default_prompt_instruction)
            print("Using system and prompt instructions from file.")
            return system_instruction, prompt_instruction
    except FileNotFoundError:
        print(f"Warning: File {file_path} not found. Using default instructions.")
        return default_system_instruction, default_prompt_instruction
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse YAML in {file_path}: {e}. Using default instructions.")
        return default_system_instruction, default_prompt_instruction
    except Exception as e:
        print(f"Error: An unexpected error occurred while reading {file_path}: {e}. Using default instructions.")
        return default_system_instruction, default_prompt_instruction

def get_diff_from_push(commit_sha):
    print(f"Debug: Starting get_diff_from_push for commit {commit_sha}")
    project = gl.projects.get(PROJECT_ID)
    try:
        commit = project.commits.get(commit_sha)
        print(f"Debug: Commit found: {commit.id}")
        if not commit.parent_ids:
            print("Debug: Initial commit, no diff.")
            return None
        parent_sha = commit.parent_ids[0]
        print(f"Debug: Parent SHA: {parent_sha}")
        diff = project.repository_compare(parent_sha, commit_sha, straight=True)
        print(f"Debug: Diff returned: {diff}")
    except Exception as e:
        print(f"Error: Failed to get diff: {e}")
        return None

    if not diff:
        print("Debug: Empty diff.")
        return None

    changed_files_content = ""
    for change in diff['diffs']:
        if "diff" in change and not change["new_file"]:
            changed_files_content += change["diff"]

    return changed_files_content

def get_diff_from_merge_request(merge_request_id):
    print(f"Debug: Starting get_diff_from_merge_request for MR {merge_request_id}")
    project = gl.projects.get(PROJECT_ID)
    try:
        merge_request = project.mergerequests.get(merge_request_id)
        if not merge_request:
            print("Debug: Merge request not found.")
            return None
        diff_changes = merge_request.changes()
    except Exception as e:
        print(f"Error: Failed to get diff for merge request: {e}")
        return None

    if not diff_changes:
        print("Debug: Empty diff.")
        return None

    changed_files_content = ""
    for change in diff_changes['changes']:
        if "diff" in change and not change["new_file"]:
           changed_files_content += change["diff"]
    return changed_files_content

def analyze_code(diff):
    print(f"Debug: system_instruction: {system_instruction}")
    print(f"Debug: prompt_instruction: {prompt_instruction}") 

    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY      
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"{prompt_instruction}\n\nDiff:\n{diff}"}
        ]
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=1.0,
                top_p=0.95,
                max_tokens=2048
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error: OpenAI failed to generate content: {e}")
            return "I'm sorry, I'm not feeling well today. Please ask a human to review this code change.\n\nError: " + str(e)
    elif GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        try:
            generation_config = {
                "temperature": 1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config=generation_config,
                system_instruction=system_instruction
            )
            prompt=f"{prompt_instruction}\n\nDiff:\n{diff}",
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error: Gemini failed to generate content: {e}")
            return "I'm sorry, I'm not feeling well today. Please ask a human to review this code change.\n\nError: " + str(e)
    else:
        print("Error: API keys not configured.")
        return "Please ask a human to check the api key."

def comment_on_commit(commit_sha, comment):
    project = gl.projects.get(PROJECT_ID)
    try:
        project.commits.get(commit_sha).comments.create({'note': comment})
        print(f"Info: Commented on commit {commit_sha}")
    except Exception as e:
        print(f"Error: Failed to create comment on commit {commit_sha}: {e}")

def comment_on_merge_request(merge_request_id, comment):
    project = gl.projects.get(PROJECT_ID)
    try:
        merge_request = project.mergerequests.get(merge_request_id)
        merge_request.notes.create({'body': comment})
        print(f"Info: Commented on merge request {merge_request_id}")
    except Exception as e:
        print(f"Error: Failed to create comment on merge request {merge_request_id}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Code Review with Gemini/OpenAI")
    parser.add_argument("--event-type", type=str, required=True, choices=["push", "merge_request"], help="Type of event (push or merge_request)")
    parser.add_argument("--commit-sha", type=str, help="SHA commit (for event type push)")
    parser.add_argument("--merge-request-id", type=int, help="Merge request ID (for event type merge_request)")
    args = parser.parse_args()

    if (not GITLAB_URL or not GITLAB_PRIVATE_TOKEN or not PROJECT_ID or (not GEMINI_API_KEY and not OPENAI_API_KEY)):
        print("Error: Required environment variables are not configured.")
        exit(1)

    if args.event_type == "push":
        if not args.commit_sha:
            print("Error: --commit-sha is required for push events.")
            return
        print(f"Info: Analyzing push commit: {args.commit_sha}")
        diff = get_diff_from_push(args.commit_sha)
        if diff:
            ai_response = analyze_code(diff)
            comment_on_commit(args.commit_sha, ai_response)

    elif args.event_type == "merge_request":
        if not args.merge_request_id:
            print("Error: --merge-request-id is required for merge_request events.")
            return
        print(f"Info: Analyzing merge request: {args.merge_request_id}")
        diff = get_diff_from_merge_request(args.merge_request_id)
        if diff:
            ai_response = analyze_code(diff)
            comment_on_merge_request(args.merge_request_id, ai_response)

if __name__ == "__main__":
    system_instruction, prompt_instruction = load_system_instruction()
    gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_PRIVATE_TOKEN)
    main()