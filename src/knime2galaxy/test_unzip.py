from parser.utils import unzip_knime_workflow

def main():
    knwf_path = "test_data/2024_nuclei_segmentation_knime.knwf"
    extract_dir = "test_data_unzipped"

    # Entpacken
    unzip_knime_workflow(knwf_path, extract_dir)



if __name__ == "__main__":
    main()