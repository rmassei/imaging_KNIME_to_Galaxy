import os

from src import parsers_functions
import pandas as pd

def merge_tsv_files(galaxy_parser_tsv, knime_parser_tsv, output_folder):
    """
    Merge galaxy and knime tsv parsed file
    """
    tsv1 = pd.read_csv(galaxy_parser_tsv, sep="\t")
    tsv2 = pd.read_csv(knime_parser_tsv, sep="\t")
    print(tsv1)
    print(tsv2)
    merged_df = pd.merge(tsv1, tsv2, left_on = "Step ID", right_on = "Unnamed: 0", how="inner")

    os.makedirs(output_folder, exist_ok=True)

    output_path = os.path.join(output_folder, "translation_table.tsv")
    merged_df.to_csv(output_path, sep="\t", index=False)

    print(f"Merged TSV saved to {output_path}")

def process_all_workflows(test_data_dir):
    """
    Loop trought all the test data
    """
    for folder in os.listdir(test_data_dir):
        folder_path = os.path.join(test_data_dir, folder)
        if os.path.isdir(folder_path):
            print(f"Processing workflow in: {folder_path}")

            workflows_path = os.path.join(folder_path, "workflows")
            knime_file = None
            galaxy_file = None

            if os.path.exists(workflows_path) and os.path.isdir(workflows_path):
                for file in os.listdir(workflows_path):
                    if file.endswith(".knwf"):
                        knime_file = os.path.join(workflows_path, file)
                    elif file.endswith(".ga"):
                        galaxy_file = os.path.join(workflows_path, file)

            if not knime_file or not galaxy_file:
                print(f"Skipping {folder_path}: Missing KNIME or Galaxy workflow file.")
                continue

            unzipped_output_path = os.path.join(folder_path, "output", "unzipped_KNIME")
            output_dir = os.path.join(folder_path, "output")
            translation_output_dir = os.path.join("../src/translation_table", folder)

            os.makedirs(unzipped_output_path, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(translation_output_dir, exist_ok=True)

            try:
                parsers_functions.extract_knime_workflow(knime_file, unzipped_output_path)
                knime_xml_file = None
                for root, _, files in os.walk(unzipped_output_path):
                    for file in files:
                        if file == "workflow.knime":
                            knime_xml_file = os.path.join(root, file)
                            break
                    if knime_xml_file:
                        break

                if not knime_xml_file:
                    raise FileNotFoundError(f"KNIME XML file not found in {unzipped_output_path}")

                parsers_functions.parse_knime_xml(knime_xml_file, output_dir)
                parsers_functions.parse_galaxy_workflow(galaxy_file, output_dir)

                knime_tsv = os.path.join(output_dir, "parsed_KNIME_nodes.tsv")
                galaxy_tsv = os.path.join(output_dir, "parsed_Galaxy_workflow_steps.tsv")
                merge_tsv_files(galaxy_tsv, knime_tsv, translation_output_dir)

                print(f"Successfully processed workflow in: {folder_path}")
            except Exception as e:
                print(f"Error processing workflow in {folder_path}: {e}")