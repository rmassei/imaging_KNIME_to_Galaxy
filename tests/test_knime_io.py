import zipfile

from imaging_knime_to_galaxy.knime_io import (
    collect_knime_node_files,
    collect_workflow_file,
    convert_knime_dict_to_string,
)


def test_convert_knime_dict_to_string() -> None:

    node_data = {
        "Node_1": "<xml>First node</xml>",
        "Node_2": "<xml>Second node</xml>",
    }

    result = convert_knime_dict_to_string(node_data)

    expected = (
        "Node ID: Node_1\n"
        "<xml>First node</xml>\n"
        "Node ID: Node_2\n"
        "<xml>Second node</xml>"
    )

    assert result == expected


def test_collect_knime_node_files_uses_nested_paths(tmp_path) -> None:
    knwf_path = tmp_path / "nested.knwf"

    with zipfile.ZipFile(knwf_path, "w") as zf:
        zf.writestr("Workflow/Image Reader (#1)/settings.xml", "<reader />")
        zf.writestr(
            "Workflow/Component (#2)/Image Reader (#1)/settings.xml",
            "<nested-reader />",
        )

    result = collect_knime_node_files(str(knwf_path))

    assert result == {
        "Component (#2)/Image Reader (#1)": "<nested-reader />",
        "Image Reader (#1)": "<reader />",
    }


def test_collect_workflow_file_includes_nested_workflows(tmp_path) -> None:
    knwf_path = tmp_path / "nested.knwf"

    with zipfile.ZipFile(knwf_path, "w") as zf:
        zf.writestr("Workflow/workflow.knime", "<root-workflow />")
        zf.writestr(
            "Workflow/Component (#2)/workflow.knime",
            "<nested-workflow />",
        )

    result = collect_workflow_file(str(knwf_path))

    assert "Workflow file: Component (#2)/workflow.knime" in result
    assert "Workflow file: workflow.knime" in result
    assert "<nested-workflow />" in result
    assert "<root-workflow />" in result
