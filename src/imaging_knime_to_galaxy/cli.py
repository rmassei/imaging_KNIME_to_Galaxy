import argparse

from imaging_knime_to_galaxy.translate import translate_knime_to_galaxy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knime2galaxy",
        description="Run KNIME-to-Galaxy workflow translation tasks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    translate_parser = subparsers.add_parser(
        "translate",
        help="Translate a KNIME .knwf workflow into a Galaxy .ga workflow.",
    )
    translate_parser.add_argument(
        "--knwf",
        required=True,
        help="Path to the input KNIME .knwf workflow.",
    )
    translate_parser.add_argument(
        "--tools-metadata",
        required=True,
        help="Path to the Galaxy tools metadata JSON file.",
    )
    translate_parser.add_argument(
        "--translation-table",
        required=True,
        help="Path to the KNIME-to-Galaxy translation examples YAML file.",
    )
    translate_parser.add_argument(
        "--workflow-examples",
        required=True,
        help="Path to the complete workflow examples YAML file.",
    )
    translate_parser.add_argument(
        "--output",
        required=True,
        help="Path where the generated Galaxy .ga workflow should be written.",
    )
    translate_parser.add_argument(
        "--input-workflow",
        required=True,
        help="Path to the Galaxy input workflow template.",
    )
    translate_parser.add_argument(
        "--vector-store",
        required=True,
        help="Path to the vector store .npz file.",
    )
    translate_parser.add_argument(
        "--example-image",
        default="../knime2galaxy_scheme.png",
        help=(
            "Path to the example image used for validation reports "
            "(default: ../knime2galaxy_scheme.png)."
        ),
    )
    translate_parser.set_defaults(func=_run_translate)

    return parser


def _run_translate(args: argparse.Namespace) -> None:
    translate_knime_to_galaxy(
        knwf_path=args.knwf,
        tools_metadata_path=args.tools_metadata,
        translation_table_path=args.translation_table,
        workflow_examples_yml_path=args.workflow_examples,
        output_galaxy_workflow_path=args.output,
        input_workflow_path=args.input_workflow,
        vector_store_path=args.vector_store,
        example_image_path=args.example_image,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
