## KNIME & Galaxy Workflow Translation Table Generator

This repository contains the code to generate translation tables from KNIME and Galaxy workflows. These tables will 
help to automate the translation of workflows between these two platforms

### Translation Table Location

All generated translation tables are stored in the directory:

`src/translation_table`

These translation tables map equivalent functionalities between KNIME nodes and Galaxy tools


### Adding Test Data and Contributing

To contribute with test data, follow these steps:

1. **Prepare Equivalent Workflows**

    - Create workflows in both KNIME and Galaxy.
    - Ensure that each KNIME node corresponds to an equivalent Galaxy tool and in the correct in sequence.

**Example:** For the case of 01_nuclei_segmentation

![KNIME_Workflow.png](src%2Ftest_data%2F01_nuclei_segmentation%2Fpics%2FKNIME_Workflow.png)
![Galaxy_workflow.png](src%2Ftest_data%2F01_nuclei_segmentation%2Fpics%2FGalaxy_workflow.png)

2. Create a New Test Data Folder

    - Create a new folder for your test case.
        
            Example: test_data/01_nuclei_segmentation
    
    - Within this folder, create two subfolders:
        - **workflows:** Store the KNIME and Galaxy workflows in this folder
        - **pics:** Include a snapshot of the workflows

3. Add workflows and images

    - Place the KNIME and Galaxy workflow files in the workflows folder
    - Add a screenshot for better documentation.

4. Execute the Code

    - Run the main script to generate the translation table:

`
python main.py
`

The translation table will be saved in `src/translation_table`


### Guidelines for Contributions

- Ensure workflows are clearly documented
- Maintain consistent naming conventions for folders and files
- Verify that the workflows are functional and the tools/nodes are or partially are equivalent

## IMPORTANT!
### KNIME nodes must be included sequentially! The order in which they appear in the workflow does not matter; what matters is the order in which the user adds them to the workflow.
