"""
Functions for implementation of a feedback loop within knime2galaxy
translation pipeline.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import yaml
from bioblend.galaxy import GalaxyInstance

from imaging_knime_to_galaxy.knime_io import (
    collect_workflow_file,
    parse_answer_as_json,
    replace_uuid,
    save_answer_to_file,
)
from imaging_knime_to_galaxy.llm_client import prompt_scadsai_llm
from imaging_knime_to_galaxy.translate import translate_knime_to_galaxy

INPUT_STEP_TYPES = {"data_input", "data_collection_input", "parameter_input"}


def read_ga_if_exists(path):
    if not path:
        raise ValueError("No .ga path provided")
    if not os.path.exists(path):
        raise FileNotFoundError(f".ga file does not exist: {path}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_error(
    stage, exc, stdout=None, stderr=None, ga_workflow=None, tb=None, extra=None
):
    return {
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "stdout": stdout,
        "stderr": stderr,
        "traceback": tb,
        "ga_workflow": ga_workflow,
        "extra": extra or {},
    }


def send_to_client(event, knime_content):
    prompt = f"""
    You are an expert in translating KNIME workflows to Galaxy workflows (.ga format).
    
    A Galaxy workflow was generated from a KNIME workflow but contains errors.
    Your task is to FIX the workflow so that it becomes valid and executable in Galaxy.
    
    Instructions:
    - Analyze the provided error information carefully.
    - Identify the root cause of the error.
    - Modify the Galaxy workflow JSON accordingly to resolve the issue.
    - Preserve as much of the original workflow structure as possible.
    - Only change what is necessary to fix the error.
    
    Output requirements:
    - Return ONLY a valid JSON object.
    - The JSON must represent a complete and corrected Galaxy workflow (.ga format).
    - Do NOT include explanations, comments, or markdown.
    - Do NOT include trailing text.
    - Ensure the JSON is syntactically valid and parsable.
    
    Galaxy workflow expectations:
    - Must include valid "steps", "connections", and "tool_id" fields where required.
    - All step references must be consistent.
    - Input/output connections must be valid.
    - Tool parameters must match expected formats.
    
    Important:
    - Use the error information to directly guide the correction.
    - If a referenced tool, parameter, or connection is invalid or missing,
      fix or replace it with a valid alternative.

    Original KNIME workflow content:
    {knime_content}
    
    Error information:
    {json.dumps(event, indent=2)}

    Output must be a valid JSON object.
    """
    response = prompt_scadsai_llm(prompt)
    print("LLM RESPONSE:\n", response)
    return response


def send_to_client_final(event, knime_content):
    prompt = f"""
    You are an expert in translating KNIME workflows to Galaxy workflows (.ga format).
    A Galaxy workflow was generated from a KNIME workflow but contains errors. 
    
    This is the FINAL step after multiple failed automatic repair attempts.
    Do NOT try to fix the workflow.
    Instead, explain clearly what is wrong and what must be changed so the
    workflow can run successfully.
    
    Respond in this format:
    
    Problem:
    - bullet points explaining the root causes of the error(s)
    
    Solution:
    - bullet points describing exactly what needs to be changed or done
    
    If the issue cannot be fixed by editing the .ga file alone
    (e.g. missing Galaxy tools), say so explicitly.
    Keep the answer concise and as short as possible. No explanations outside
    the bullet points.
    
    KNIME workflow:
    {knime_content}
    
    Error:
    {json.dumps(event, indent=2)}
    """
    response = prompt_scadsai_llm(prompt)
    print("LLM RESPONSE:\n", response)
    return response


def run_stage(
    stage_name,
    knime_content,
    func,
    *args,
    ga_workflow=None,
    output_galaxy_workflow_path=None,
    **kwargs,
):
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        error_info = build_error(stage_name, exc, ga_workflow=ga_workflow)
        print(f"Error found in {stage_name}, sending error to client ...")
        response = send_to_client({"type": "error", "data": error_info}, knime_content)

        if output_galaxy_workflow_path is not None:
            process_response(response, output_galaxy_workflow_path)

        raise


def process_response(answer, output_galaxy_workflow_path):
    if not answer:
        raise ValueError("LLM returned an empty response")

    json_object = parse_answer_as_json(answer)
    replace_uuid(json_object)

    p = Path(output_galaxy_workflow_path)
    save_answer_to_file(json_object, output_path=str(p))
    return str(p)


def _iteration_feedback_path(base_path, iteration):
    p = Path(base_path)
    return p.with_name(f"{p.stem}_iter{iteration}{p.suffix}")


def _iteration_labeled_path(base_path, iteration):
    p = Path(base_path)
    return p.with_name(f"{p.stem}_iter{iteration}_labeled{p.suffix}")


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)

    return result


def generate_job_yaml(ga_path, output_path, default_file):
    ga_path = Path(ga_path)
    output_path = Path(output_path)
    default_file = str(Path(default_file).resolve())

    with ga_path.open("r", encoding="utf-8") as f:
        workflow = json.load(f)

    job = {}
    for step_id, step in workflow.get("steps", {}).items():
        if step.get("type") in INPUT_STEP_TYPES:
            key = step.get("label") or f"input_{step_id}"
            job[key] = {
                "class": "File",
                "path": default_file,
            }

    if not job:
        raise ValueError(f"No workflow inputs found in {ga_path}")

    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(job, f, sort_keys=False)

    print(f"job.yml written to {output_path}")
    print(yaml.safe_dump(job, sort_keys=False))


def add_missing_input_labels(
    ga_path: str | Path, output_path: str | Path | None = None
):
    ga_path = Path(ga_path)
    output_path = ga_path if output_path is None else Path(output_path)

    with ga_path.open("r", encoding="utf-8") as f:
        workflow = json.load(f)

    steps = workflow.get("steps", {})
    changed = []

    for step_id, step in steps.items():
        if step.get("type") in INPUT_STEP_TYPES and not step.get("label"):
            label = f"input_{step_id}"
            step["label"] = label
            changed.append((step_id, label))

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2)

    print(f"Patched workflow written to {output_path}")
    if changed:
        print("Added labels:")
        for step_id, label in changed:
            print(f"  step {step_id} -> {label}")
    else:
        print("No missing input labels found.")


def extract_invocation_id(planemo_stdout: str) -> str | None:
    if not planemo_stdout:
        return None
    match = re.search(r"/workflows/invocations/([a-f0-9]+)", planemo_stdout)
    if match:
        return match.group(1)

    return None


def fetch_galaxy_invocation_debug(
    invocation_id: str, galaxy_url: str, api_key: str
) -> dict:
    gi = GalaxyInstance(url=galaxy_url, key=api_key)

    debug = {
        "invocation_id": invocation_id,
        "invocation": None,
        "invocation_steps": None,
        "jobs_summary": None,
        "job_details": [],
        "fetch_errors": [],
    }

    try:
        # Basic invocation info
        invocation = gi.workflows.show_invocation(invocation_id)
        debug["invocation"] = invocation
    except Exception as exc:
        debug["fetch_errors"].append(f"show_invocation failed: {exc}")
        return debug

    # Try to get more detailed step data via raw GET
    try:
        raw_steps = gi.make_get_request(
            f"{gi.url}/api/invocations/{invocation_id}", params={"step_details": True}
        )
        debug["invocation_steps"] = raw_steps.get("steps")
    except Exception as exc:
        debug["fetch_errors"].append(f"step_details fetch failed: {exc}")

    # Try to collect job ids from invocation steps
    job_ids = set()

    steps = debug["invocation_steps"]
    if steps is None and isinstance(invocation, dict):
        steps = invocation.get("steps", [])

    if steps:
        for step in steps:
            if not isinstance(step, dict):
                continue

            # Depending on Galaxy version, job info may appear in different places
            if step.get("job_id"):
                job_ids.add(step["job_id"])

            jobs = step.get("jobs", [])
            if isinstance(jobs, list):
                for job in jobs:
                    if isinstance(job, dict) and job.get("id"):
                        job_ids.add(job["id"])

    # Fetch detailed job info
    for job_id in job_ids:
        try:
            job_info = gi.jobs.show_job(job_id, full_details=True)
            debug["job_details"].append(job_info)
        except Exception as exc:
            debug["fetch_errors"].append(f"show_job failed for {job_id}: {exc}")

    return debug


def translate_feedback(
    knwf_path,
    tools_metadata_path,
    translation_table_path,
    workflow_examples_yml_path,
    output_galaxy_workflow_path,
    output_galaxy_workflow_path_labeled,
    input_workflow_path,
    vector_store_path,
    input_image_path,
    job_yml_path,
    max_iterations=3,
):
    record = {
        "knime_file": knwf_path,
        "status": "failed",
        "failed_stage": None,
        "error_raw": None,
        "lint_stdout": None,
        "lint_stderr": None,
        "planemo_stdout": None,
        "planemo_stderr": None,
        "iterations": [],
    }

    knime_content = collect_workflow_file(knwf_path)

    if not os.path.exists(input_image_path):
        record["failed_stage"] = "generate_job_yml"
        record["error_raw"] = f"Input image does not exist: {input_image_path}"
        return record

    if "GALAXY_API_KEY" not in os.environ:
        record["failed_stage"] = "planemo_run"
        record["error_raw"] = "Environment variable GALAXY_API_KEY is not set"
        return record

    try:
        translate_knime_to_galaxy(
            knwf_path,
            tools_metadata_path,
            translation_table_path,
            workflow_examples_yml_path,
            output_galaxy_workflow_path,
            input_workflow_path,
            vector_store_path,
        )
    except Exception as exc:
        record["failed_stage"] = "convert_to_ga"
        record["error_raw"] = str(exc)
        return record

    current_ga_path = Path(output_galaxy_workflow_path)
    original_ga_path = Path(output_galaxy_workflow_path)

    for iteration in range(1, max_iterations + 1):
        iteration_info = {
            "iteration": iteration,
            "ga_path": str(current_ga_path),
            "failed_stage": None,
            "error_raw": None,
        }
        try:
            stage = "read_ga_file"
            ga_workflow = read_ga_if_exists(current_ga_path)

        except Exception as exc:
            err = build_error(
                stage,
                exc,
                ga_workflow=None,
                extra={"ga_path": str(current_ga_path)},
            )
            response = send_to_client({"type": "error", "data": err}, knime_content)
            repaired_path = process_response(
                response,
                _iteration_feedback_path(original_ga_path, iteration),
            )
            iteration_info["failed_stage"] = "read_ga_file"
            iteration_info["error_raw"] = err["message"]
            record["iterations"].append(iteration_info)
            current_ga_path = Path(repaired_path)
            continue

        try:
            stage = "workflow_lint"
            lint_result = run_command(
                [
                    "planemo",
                    "workflow_lint",
                    "--report_level",
                    "error",
                    "--fail_level",
                    "error",
                    str(current_ga_path),
                ]
            )
            record["lint_stdout"] = lint_result.stdout
            record["lint_stderr"] = lint_result.stderr

            if lint_result.returncode != 0:
                err = build_error(
                    "workflow_lint",
                    RuntimeError("workflow_lint failed"),
                    stdout=lint_result.stdout,
                    stderr=lint_result.stderr,
                    ga_workflow=ga_workflow,
                )
                response = send_to_client({"type": "error", "data": err}, knime_content)
                repaired_path = process_response(
                    response,
                    _iteration_feedback_path(original_ga_path, iteration),
                )
                iteration_info["failed_stage"] = "workflow_lint"
                iteration_info["error_raw"] = err["message"]
                record["iterations"].append(iteration_info)
                current_ga_path = Path(repaired_path)
                continue

            labeled_path = _iteration_labeled_path(original_ga_path, iteration)
            add_missing_input_labels(current_ga_path, labeled_path)

            try:
                stage = "read_labeled_ga_file"
                ga_workflow = read_ga_if_exists(labeled_path)
            except Exception as exc:
                err = build_error(
                    stage,
                    exc,
                    ga_workflow=None,
                    extra={"ga_path": str(labeled_path)},
                )
                response = send_to_client({"type": "error", "data": err}, knime_content)
                repaired_path = process_response(
                    response,
                    _iteration_feedback_path(original_ga_path, iteration),
                )
                iteration_info["failed_stage"] = "read_labeled_ga_file"
                iteration_info["error_raw"] = err["message"]
                record["iterations"].append(iteration_info)
                current_ga_path = Path(repaired_path)
                continue

            generate_job_yaml(labeled_path, job_yml_path, input_image_path)

            planemo_result = run_command(
                [
                    "planemo",
                    "run",
                    str(labeled_path),
                    str(job_yml_path),
                    "--engine",
                    "external_galaxy",
                    "--galaxy_url",
                    "https://usegalaxy.eu",
                    "--galaxy_user_key",
                    os.environ["GALAXY_API_KEY"],
                ]
            )
            record["planemo_stdout"] = planemo_result.stdout
            record["planemo_stderr"] = planemo_result.stderr

            if planemo_result.returncode != 0:
                invocation_id = extract_invocation_id(planemo_result.stdout)

                galaxy_debug = None
                if invocation_id:
                    try:
                        galaxy_debug = fetch_galaxy_invocation_debug(
                            invocation_id=invocation_id,
                            galaxy_url="https://usegalaxy.eu",
                            api_key=os.environ["GALAXY_API_KEY"],
                        )
                    except Exception as debug_exc:
                        galaxy_debug = {
                            "invocation_id": invocation_id,
                            "fetch_error": str(debug_exc),
                        }

                err = build_error(
                    stage,
                    RuntimeError("planemo run failed"),
                    stdout=planemo_result.stdout,
                    stderr=planemo_result.stderr,
                    ga_workflow=ga_workflow,
                    tb=None,
                    extra={
                        "invocation_id": invocation_id,
                        "galaxy_debug": galaxy_debug,
                        "job_yml_path": str(job_yml_path),
                    },
                )
                err["galaxy_debug"] = galaxy_debug
                response = send_to_client({"type": "error", "data": err}, knime_content)
                repaired_path = process_response(
                    response,
                    _iteration_feedback_path(original_ga_path, iteration),
                )
                iteration_info["failed_stage"] = "planemo_run"
                iteration_info["error_raw"] = err["message"]
                record["iterations"].append(iteration_info)
                current_ga_path = Path(repaired_path)
                continue

            record["status"] = "success"
            record["failed_stage"] = None
            record["error_raw"] = None
            record["iterations"].append(iteration_info)
            return record

        except Exception as exc:
            iteration_info["failed_stage"] = stage
            iteration_info["error_raw"] = str(exc)
            record["iterations"].append(iteration_info)
            continue

    # send the last error information to the LLM to get back advice
    response = send_to_client_final({"type": "error", "data": err}, knime_content)

    record["failed_stage"] = (
        record["iterations"][-1]["failed_stage"] if record["iterations"] else None
    )
    record["error_raw"] = f"Maximum iterations ({max_iterations}) reached"
    record["suggestion"] = response
    return record
