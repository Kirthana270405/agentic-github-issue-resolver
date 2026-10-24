# Agentic GitHub Issue Resolver

An AI-powered Python project that experiments with automating GitHub issue resolution through a structured workflow: analyzing an issue, planning code changes, generating a patch, validating it, applying it, and running tests.

## Features

- **Issue analysis and planning:** Uses an agent workflow to identify proposed code changes.
- **AI code generation:** Uses a locally hosted Ollama model to generate candidate patches.
- **Patch validation:** Checks generated changes before application.
- **Controlled patch application:** Applies validated changes in a controlled repository workspace.
- **Test execution:** Runs repository tests to help verify proposed changes.
- **Workflow orchestration:** Coordinates the resolution stages and tracks their outcomes.
- **Local demonstration:** Includes scripts for demonstrating and testing the workflow.

## Architecture

The project is organized into agent components and workflow orchestration.

```text
GitHub Issue / Problem Description
              |
              v
      Issue Analysis
              |
              v
       Implementation Plan
              |
              v
       Code Generation
              |
              v
       Patch Validation
              |
              v
       Patch Application
              |
              v
        Test Execution
              |
              v
      Workflow Result
```

The workflow may stop when it cannot produce a valid patch or when a stage fails. A generated patch is not, by itself, proof that the underlying issue has been fixed.

## Technology Stack

- Python
- Ollama for local language-model inference
- Qwen3 1.7B (`qwen3:1.7b`) as the configured model
- Pytest for automated testing
- Git and GitHub for source control and repository collaboration

## Prerequisites

- Python installed
- Git installed
- Ollama installed and running
- The configured model available locally

Pull the model if it is not already installed:

```powershell
ollama pull qwen3:1.7b
```

## Setup

Clone the repository and enter its directory:

```powershell
git clone https://github.com/Kirthana270405/agentic-github-issue-resolver.git
cd agentic-github-issue-resolver
```

Create and activate a virtual environment on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project's dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start Ollama if it is not already running, and ensure the configured model is available.

## Run the Demonstrations

Run the controlled workflow demonstration:

```powershell
python run_controlled_test.py
```

Run the local demonstration:

```powershell
python run_local_demo.py
```

These scripts demonstrate the workflow in controlled environments. Review their output to see whether patch generation, validation, application, and testing succeeded.

## Run the Tests

Run the project's automated test suite:

```powershell
python -m pytest -q
```

The full suite previously completed with **46 passing tests** during development. Test results can change as the code or environment changes.

The controlled demonstration also previously completed with three passing tests in its isolated repository.

## Current Status and Limitations

This project is a working prototype, not a production-ready autonomous software engineer.

- Successful controlled demonstrations do not guarantee successful resolution of arbitrary GitHub issues.
- Real-world issue evaluation has been inconsistent. In an earlier evaluation of three Requests issues, none produced an applied patch.
- Some issues may lack sufficient context, exceed planning time limits, or result in invalid or unchanged generated patches.
- Automated GitHub pull-request creation encountered a GitHub API permission restriction in the development environment.
- Review generated changes carefully before merging or deploying them.
- Model output quality depends on the issue description, repository context, and locally configured model.

The project is intended to demonstrate agent orchestration, AI-assisted code generation, patch validation, controlled code modification, and test-driven verification.

## Future Improvements

- Improve issue understanding and implementation planning.
- Add stronger repository-aware context retrieval.
- Improve patch generation retries and failure diagnostics.
- Expand regression tests for real-world issues.
- Improve GitHub API permissions handling and pull-request automation.
- Evaluate patch correctness using reproducible benchmarks.

## License

See the repository's license file, if provided.
