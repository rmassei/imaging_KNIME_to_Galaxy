from imaging_knime_to_galaxy.knime_io import convert_knime_dict_to_string


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
