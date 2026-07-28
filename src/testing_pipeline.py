from pathlib import Path
import traceback
import re
import pandas as pd
from imaging_knime_to_galaxy.translate import translate_knime_to_galaxy
from imaging_knime_to_galaxy.evaluation_functions import add_missing_input_labels, generate_job_yaml, run_command, testing_report, extract_error_message
import subprocess
import os
import json
import yaml

DATA_FOLDER = Path("../data").resolve()
N_RUNS = 1
KNIME_FOLDER = DATA_FOLDER / "train_data_workflows" / "KNIME_2"
JOB_YML = DATA_FOLDER / "job.yml"
OUTPUT_FOLDER = DATA_FOLDER / "planemo_test"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
IMAGE = Path("../knime2galaxy_scheme.png").resolve()

def run_single_pipeline(knime_file: Path, run_idx: int) -> dict:
    record = {
        "knime_file": str(knime_file),
        "file_name": knime_file.name,
        "run_idx": run_idx,
        "status": "success",
        "failed_stage": None,
        "error_raw": None,
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
        history_name = f"pipeline_{knime_file.stem}_run_{run_idx}"
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
            "--history_name", history_name,
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

    return pd.DataFrame(results)


def summarize_errors(df: pd.DataFrame):
    failed = df[df["status"] == "failed"].copy()

    stage_error_counts = (
        failed.groupby(["failed_stage"])
        .size()
        .reset_index(name="count")
        .sort_values(["failed_stage", "count"], ascending=[True, False])
    )

    file_error_counts = (
        failed.groupby(["file_name"])
        .size()
        .reset_index(name="count")
        .sort_values(["file_name", "count"], ascending=[True, False])
    )

    return stage_error_counts, file_error_counts


if __name__ == "__main__":
    df_results = run_batch(KNIME_FOLDER, N_RUNS)

    stage_error_counts, file_error_counts = summarize_errors(df_results)

    print("\nOverall status:")
    print(df_results["status"].value_counts())

    print("\nErrors by stage:")
    print(stage_error_counts)

    print("\nErrors by file:")
    print(file_error_counts)

    df_results.to_csv(os.path.join(DATA_FOLDER,f"n={N_RUNS}_run_results.csv"), index=False)
    stage_error_counts.to_csv(os.path.join(DATA_FOLDER,f"n={N_RUNS}_stage_error_counts.csv"), index=False)
    file_error_counts.to_csv(os.path.join(DATA_FOLDER,f"n={N_RUNS}_file_error_counts.csv"), index=False)