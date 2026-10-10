
import pytest

from app.workflow.graph import (
    MAX_RETRIES,
    route_after_debug,
    route_after_tests,
)
from app.workflow.nodes import prepare_retry_node


def test_failed_tests_route_to_debug():
    state = {
        "repository_test_result": {
            "success": False,
            "skipped": False,
        },
        "retry_count": 0,
    }

    assert route_after_tests(state) == "debug"


def test_successful_tests_stop_workflow():
    state = {
        "repository_test_result": {
            "success": True,
            "skipped": False,
        },
        "retry_count": 0,
    }

    assert route_after_tests(state) == "finish"


def test_failed_tests_stop_at_retry_limit():
    state = {
        "repository_test_result": {
            "success": False,
            "skipped": False,
        },
        "retry_count": MAX_RETRIES,
    }

    assert route_after_tests(state) == "finish"


def test_safe_code_diagnosis_triggers_retry():
    state = {
        "debug_analysis": {
            "category": "code",
            "retry_recommended": True,
        },
        "retry_count": 0,
    }

    assert route_after_debug(state) == "prepare_retry"


def test_unsafe_diagnosis_does_not_trigger_retry():
    state = {
        "debug_analysis": {
            "category": "environment",
            "retry_recommended": True,
        },
        "retry_count": 0,
    }

    assert route_after_debug(state) == "finish"


def test_debug_retry_stops_at_retry_limit():
    state = {
        "debug_analysis": {
            "category": "code",
            "retry_recommended": True,
        },
        "retry_count": MAX_RETRIES,
    }

    assert route_after_debug(state) == "finish"


def test_prepare_retry_increments_counter_and_clears_old_results():
    state = {
        "retry_count": 0,
        "generated_patches": [{"file_path": "example.py"}],
        "patch_validation_results": [{"valid": True}],
        "patch_application_results": [{"applied": True}],
        "test_results": [{"success": False}],
        "repository_test_result": {"success": False},
        "final_status": "success",
    }

    result = prepare_retry_node(state)

    assert result["retry_count"] == 1
    assert result["generated_patches"] == []
    assert result["patch_validation_results"] == []
    assert result["patch_application_results"] == []
    assert result["test_results"] == []
    assert result["repository_test_result"] == {}
    assert result["final_status"] == ""
