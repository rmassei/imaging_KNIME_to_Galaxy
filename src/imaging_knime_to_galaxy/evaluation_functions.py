from pathlib import Path
import traceback
import re
import pandas as pd
import subprocess
import os
import json
import yaml

DATA_FOLDER = Path("../data").resolve()
OUTPUT_FOLDER = DATA_FOLDER / "output_file_test"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
INPUT_STEP_TYPES = {"data_input", "data_collection_input", "parameter_input"}

JOB_YML = DATA_FOLDER / "job.yml"
IMAGE = DATA_FOLDER / "image_ex.jpg"


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


def add_missing_input_labels(ga_path: str | Path, output_path: str | Path | None = None):
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

    print(f"Updated workflow with new input labels written to {output_path}")

    
def extract_error_message(exc: Exception) -> str:
    if exc is None:
        return "UNKNOWN_ERROR"

    msg = str(exc).strip()
    if msg:
        return msg

    return "".join(traceback.format_exception_only(type(exc), exc)).strip()


def run_command(cmd: list[str], stage: str) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        full_msg = (
            f"{stage} failed with return code {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )
        raise RuntimeError(full_msg)

    return result


def testing_report(
    output_galaxy_workflow_path: str,
    knime_file: Path,
    job_yml_path: Path,
    input_image_path: Path,
):
    output_galaxy_workflow_path = Path(output_galaxy_workflow_path)
    knime_file = Path(knime_file)
    job_yml_path = Path(job_yml_path)
    input_image_path = Path(input_image_path)

    record = {
        "file_name": knime_file.name,
        "status": "success",
        "failed_stage": None,
        "error_raw": None,
        "job_yml_path": str(job_yml_path),
        "lint_stdout": None,
        "lint_stderr": None,
        "planemo_stdout": None,
        "planemo_stderr": None,
    }

    stage = None

    try:
        output_galaxy_workflow_path = Path(output_galaxy_workflow_path)
        output_galaxy_workflow_path_labeled = output_galaxy_workflow_path.with_name(f"{output_galaxy_workflow_path.stem}_labeled.ga")

        stage = "workflow_lint"
        lint_result = run_command(
            [
                "planemo",
                "workflow_lint",
                "--report_level", "error",
                "--fail_level", "error",
                str(output_galaxy_workflow_path),
            ],
            stage,
        )

        record["lint_stdout"] = lint_result.stdout
        record["lint_stderr"] = lint_result.stderr

        if lint_result.returncode != 0:
            raise RuntimeError(
                f"workflow_lint failed\n"
                f"STDOUT:\n{lint_result.stdout}\n\n"
                f"STDERR:\n{lint_result.stderr}"
            )

        stage = "label_ga"
        add_missing_input_labels(
            output_galaxy_workflow_path,
            output_galaxy_workflow_path_labeled,
        )

        if not Path(output_galaxy_workflow_path_labeled).exists():
            raise RuntimeError(
                f"Labeled workflow was not created: "
                f"{output_galaxy_workflow_path_labeled}"
            )

        stage = "generate_job_yml"
        if not input_image_path.exists():
            raise FileNotFoundError(
                f"Input image does not exist: {input_image_path}"
            )

        generate_job_yaml(
            output_galaxy_workflow_path_labeled,
            job_yml_path,
            input_image_path,
        )

        stage = "planemo_run"
        if "GALAXY_API_KEY" not in os.environ:
            raise RuntimeError(
                "Environment variable GALAXY_API_KEY is not set"
            )

        cmd = [
            "planemo",
            "run",
            str(output_galaxy_workflow_path_labeled),
            str(job_yml_path),
            "--engine", "external_galaxy",
            "--galaxy_url", "https://usegalaxy.eu",
            "--galaxy_user_key", os.environ["GALAXY_API_KEY"],
        ]

        planemo_result = run_command(cmd, stage)

        record["planemo_stdout"] = planemo_result.stdout
        record["planemo_stderr"] = planemo_result.stderr

    except Exception as e:
        record["status"] = "failed"
        record["failed_stage"] = stage
        record["error_raw"] = str(e)

    return record