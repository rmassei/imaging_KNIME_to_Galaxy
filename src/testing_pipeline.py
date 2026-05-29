from pathlib import Path
import traceback
import re
import pandas as pd
from imaging_knime_to_galaxy.translate import translate_knime_to_galaxy
import subprocess
import os
import json
import yaml

DATA_FOLDER = Path("../data").resolve()
KNIME_FOLDER = DATA_FOLDER / "train_data_workflows" / "KNIME_2"
OUTPUT_FOLDER = DATA_FOLDER / "output_file_test"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

N_RUNS = 1
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
    print(yaml.safe_dump(job, sort_keys=False))


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

    print(f"Patched workflow written to {output_path}")
    if changed:
        print("Added labels:")
        for step_id, label in changed:
            print(f"  step {step_id} -> {label}")
    else:
        print("No missing input labels found.")


def normalize_error_message(msg: str) -> str:
    if not msg:
        return "UNKNOWN_ERROR"

    msg = msg.strip()

    patterns = [
        (
            r"Workflow cannot be run because input step '.*?' \(.*?\) is not optional and no input provided\.",
            "Missing required workflow input",
        ),
        (
            r"No content id could be located for step .*",
            "Missing content_id/tool_id",
        ),
        (
            r"File \[.*\] does not exist.*",
            "Input file does not exist",
        ),
        (
            r"Parameter '.*?': specify a dataset of the required format / build for parameter",
            "Wrong dataset format for tool parameter",
        ),
        (
            r"No value found for '.*?'\. Using default:",
            "Missing tool parameter value",
        ),
        (
            r"Java heap space",
            "KNIME out of memory",
        ),
        (
            r"Node can't be executed - Node .* not available from extension .*",
            "Missing KNIME extension",
        ),
        (
            r"There were problems with \d+ test\(s\)",
            "Planemo run/test reported workflow failures",
        ),
        (
            r"Run failed \[.*\]",
            "Planemo run failed",
        ),
    ]

    for pattern, label in patterns:
        if re.search(pattern, msg, flags=re.DOTALL):
            return label

    return msg.splitlines()[0][:300]


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


def run_single_pipeline(knime_file: Path, run_idx: int) -> dict:
    record = {
        "knime_file": str(knime_file),
        "file_name": knime_file.name,
        "run_idx": run_idx,
        "status": "success",
        "failed_stage": None,
        "error_raw": None,
        "error_normalized": None,
        "ga_path": None,
        "ga_labeled_path": None,
        "job_yml_path": str(JOB_YML),
        "lint_stdout": None,
        "lint_stderr": None,
        "planemo_stdout": None,
        "planemo_stderr": None,
    }

    output_galaxy_workflow_path = OUTPUT_FOLDER / f"{knime_file.stem}_{run_idx}.ga"
    output_galaxy_workflow_path_labeled = OUTPUT_FOLDER / f"{knime_file.stem}_{run_idx}_labeled.ga"

    record["ga_path"] = str(output_galaxy_workflow_path)
    record["ga_labeled_path"] = str(output_galaxy_workflow_path_labeled)

    try:
        stage = "convert_to_ga"
        if not output_galaxy_workflow_path.exists():
            translate_knime_to_galaxy(
                knwf_path=knime_file,
                tools_metadata_path=DATA_FOLDER / "tools_metadata.json",
                translation_table_path=DATA_FOLDER / "translation_table.yml",
                workflow_examples_yml_path=DATA_FOLDER / "workflow_translation_table.yml",
                output_galaxy_workflow_path=output_galaxy_workflow_path,
                input_workflow_path=DATA_FOLDER / "input_workflows.ga",
                vector_store_path=DATA_FOLDER / "vector_store.npz",
            )
        else:
            print(f"Skipping conversion, file already exists: {output_galaxy_workflow_path}")

        if not output_galaxy_workflow_path.exists():
            raise RuntimeError(f"Translated workflow was not created: {output_galaxy_workflow_path}")

        stage = "workflow_lint"
        lint_result = run_command(
            ["planemo", "workflow_lint", "--report_level", "error", "--fail_level", "error", str(output_galaxy_workflow_path)], stage,
        )
        # fetch errors/output
        stdout = lint_result.stdout
        stderr = lint_result.stderr
        
        record["lint_stdout"] = stdout
        record["lint_stderr"] = stderr

        if lint_result.returncode != 0:
            raise RuntimeError(
                f"workflow_lint failed\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
            )
        else:
            print(f"Lint passed (errors only, warnings ignored)")
    
        stage = "label_ga"
        add_missing_input_labels(
            output_galaxy_workflow_path,
            output_galaxy_workflow_path_labeled,
        )

        if not output_galaxy_workflow_path_labeled.exists():
            raise RuntimeError(f"Labeled workflow was not created: {output_galaxy_workflow_path_labeled}")

        stage = "generate_job_yml"
        if not IMAGE.exists():
            raise FileNotFoundError(f"Input image does not exist: {IMAGE}")

        generate_job_yaml(output_galaxy_workflow_path_labeled, JOB_YML, IMAGE)

        stage = "planemo_run"
        if "GALAXY_API_KEY" not in os.environ:
            raise RuntimeError("Environment variable GALAXY_API_KEY is not set")

        cmd = [
            "planemo",
            "run",
            str(output_galaxy_workflow_path_labeled),
            str(JOB_YML),
            "--engine", "external_galaxy",
            "--galaxy_url", "https://usegalaxy.eu",
            "--galaxy_user_key", os.environ["GALAXY_API_KEY"],
        ]

        planemo_result = run_command(cmd, stage)
        record["planemo_stdout"] = planemo_result.stdout
        record["planemo_stderr"] = planemo_result.stderr

        return record

    except Exception as exc:
        raw_error = extract_error_message(exc)
    
        record["status"] = "failed"
        record["failed_stage"] = stage
        record["error_raw"] = raw_error
        record["error_normalized"] = normalize_error_message(raw_error)
        return record


def run_batch(knime_folder: Path, n_runs: int) -> pd.DataFrame:
    results = []
    knime_files = sorted(knime_folder.glob("*.knwf"))

    if not knime_files:
        raise FileNotFoundError(f"No .knwf files found in {knime_folder}")

    for knime_file in knime_files:
        for run_idx in range(1, n_runs + 1):
            print(f"\n=== Running {knime_file.name} | iteration {run_idx}/{n_runs} ===")
            result = run_single_pipeline(knime_file, run_idx)
            results.append(result)
            print(f"Result: {result['status']}")
            print(f"Planemo Result: {result['planemo_stdout']}")
            if result["status"] == "failed":
                print(f"Failed stage: {result['failed_stage']}")
                print(f"Error bucket: {result['error_normalized']}")

    return pd.DataFrame(results)


def summarize_errors(df: pd.DataFrame):
    failed = df[df["status"] == "failed"].copy()

    error_counts = (
        failed["error_normalized"]
        .value_counts(dropna=False)
        .rename_axis("error_type")
        .reset_index(name="count")
    )

    stage_error_counts = (
        failed.groupby(["failed_stage", "error_normalized"])
        .size()
        .reset_index(name="count")
        .sort_values(["failed_stage", "count"], ascending=[True, False])
    )

    file_error_counts = (
        failed.groupby(["file_name", "error_normalized"])
        .size()
        .reset_index(name="count")
        .sort_values(["file_name", "count"], ascending=[True, False])
    )

    return error_counts, stage_error_counts, file_error_counts


if __name__ == "__main__":
    df_results = run_batch(KNIME_FOLDER, N_RUNS)

    error_counts, stage_error_counts, file_error_counts = summarize_errors(df_results)

    print("\nOverall status:")
    print(df_results["status"].value_counts())

    print("\nMost common error types:")
    print(error_counts)

    print("\nErrors by stage:")
    print(stage_error_counts)

    print("\nErrors by file:")
    print(file_error_counts)

    df_results.to_csv(os.path.join(DATA_FOLDER,f"pipeline_n={N_RUNS}_run_results.csv"), index=False)
    error_counts.to_csv(os.path.join(DATA_FOLDER,f"n={N_RUNS}_error_counts.csv"), index=False)
    stage_error_counts.to_csv(os.path.join(DATA_FOLDER,f"n={N_RUNS}_stage_error_counts.csv"), index=False)
    file_error_counts.to_csv(os.path.join(DATA_FOLDER,f"n={N_RUNS}_file_error_counts.csv"), index=False)