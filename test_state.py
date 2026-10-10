from app.workflow.state import WorkflowState


state: WorkflowState = {
    "owner": "psf",
    "repo": "requests",
    "issue_number": 1,
    "issue_title": "Cookie support?",
    "issue_body": "Add cookie support."
}

print("Workflow state created successfully.")
print(state)