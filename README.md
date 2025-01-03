# AI Code Review

This project is an AI-powered code review tool that integrates with GitLab and uses various AI models to provide detailed code reviews. The tool is designed to help developers improve code quality by focusing on clarity, structure, and security.

## Features
- Integrates with GitLab for seamless code review process
- Utilizes AI models from OpenAI and Google Gemini for generating code review feedback
- Customizable system instructions via a YAML configuration file
- Environment variable support for configuration

## Example Usage with Docker

You can use the Docker image `flaviohcardoso/ai-code-review` to run the AI code review tool. Here is an example GitLab CI configuration:

```yaml
stages:
  - code_review

code_review_merge_request:
  stage: code_review
  image: flaviohcardoso/ai-code-review:latest
  only:
    - merge_requests
  script:
    - python /usr/src/app/ai-code-review.py --event-type merge_request --merge-request-id $CI_MERGE_REQUEST_IID
```

## Configuration
The following environment variables need to be added to your GitLab CI/CD settings:

`GITLAB_URL`
`GITLAB_PRIVATE_TOKEN`
`GEMINI_API_KEY`
`OPENAI_API_KEY` (if using OpenAI models)

To add these variables, go to your GitLab project, navigate to **Settings > CI/CD > Variables**, and add each variable with its corresponding value.