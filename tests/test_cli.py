import pytest

from imaging_knime_to_galaxy import cli

TRANSLATE_ARGS = [
    "translate",
    "--knwf",
    "data/input.knwf",
    "--tools-metadata",
    "data/tools_metadata.json",
    "--translation-table",
    "data/translation_table.yml",
    "--workflow-examples",
    "data/workflow_translation_table.yml",
    "--output",
    "data/output.ga",
    "--input-workflow",
    "data/input_workflows.ga",
    "--vector-store",
    "data/vector_store.npz",
]


def test_build_parser_parses_translate_arguments() -> None:
    parser = cli.build_parser()

    args = parser.parse_args([*TRANSLATE_ARGS, "--example-image", "image.png"])

    assert args.command == "translate"
    assert args.knwf == "data/input.knwf"
    assert args.tools_metadata == "data/tools_metadata.json"
    assert args.translation_table == "data/translation_table.yml"
    assert args.workflow_examples == "data/workflow_translation_table.yml"
    assert args.output == "data/output.ga"
    assert args.input_workflow == "data/input_workflows.ga"
    assert args.vector_store == "data/vector_store.npz"
    assert args.example_image == "image.png"


def test_build_parser_uses_default_example_image() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(TRANSLATE_ARGS)

    assert args.example_image == "../knime2galaxy_scheme.png"


def test_build_parser_requires_translate_arguments() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["translate"])

    assert exc_info.value.code == 2


def test_main_calls_translate_knime_to_galaxy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_translate_knime_to_galaxy(**kwargs: str) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        cli,
        "translate_knime_to_galaxy",
        fake_translate_knime_to_galaxy,
    )

    exit_code = cli.main([*TRANSLATE_ARGS, "--example-image", "image.png"])

    assert exit_code == 0
    assert calls == [
        {
            "knwf_path": "data/input.knwf",
            "tools_metadata_path": "data/tools_metadata.json",
            "translation_table_path": "data/translation_table.yml",
            "workflow_examples_yml_path": "data/workflow_translation_table.yml",
            "output_galaxy_workflow_path": "data/output.ga",
            "input_workflow_path": "data/input_workflows.ga",
            "vector_store_path": "data/vector_store.npz",
            "example_image_path": "image.png",
        }
    ]
