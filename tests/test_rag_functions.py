from imaging_knime_to_galaxy.rag_functions import search_store_for_hits


class FakeVectorStore:
    """Returns one distinct hit per query, so hits can be traced to a step."""

    def __init__(self):
        self.queries = []

    def search(self, query, k=3):
        self.queries.append(query)
        return [
            {"text": f"{query} tool", "meta": {"guid": f"guid_{query}"}},
        ]


def test_search_store_for_hits_keeps_every_step() -> None:

    store = FakeVectorStore()

    hits = search_store_for_hits("segment image; measure objects; export table", store)

    assert store.queries == ["segment image", "measure objects", "export table"]
    assert [h["meta"]["guid"] for h in hits] == [
        "guid_segment image",
        "guid_measure objects",
        "guid_export table",
    ]


def test_search_store_for_hits_deduplicates_by_guid() -> None:

    store = FakeVectorStore()

    hits = search_store_for_hits("segment image; segment image", store)

    assert len(hits) == 1


def test_search_store_for_hits_without_steps() -> None:

    store = FakeVectorStore()

    assert search_store_for_hits("   ", store) == []
