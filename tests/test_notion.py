import pytest

from gra import notion

PAGE_ID = "3fea39e7-3411-819e-bc7e-c5b1761f5e2e"


@pytest.mark.parametrize(
    "arg",
    [
        "https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e",
        "https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e?pvs=204",
        "app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e",
        "https://www.notion.so/Introduction-to-tensor-core-arithmetic-3fea39e73411819ebc7ec5b1761f5e2e",
        "https://www.notion.so/myspace/Introduction-3fea39e73411819ebc7ec5b1761f5e2e?pvs=4#abc",
        "https://www.notion.so/3fea39e73411819ebc7ec5b1761f5e2e/",
        "https://www.notion.so/3f3a39e73411802ab0b1c942a2416bb7?v=1234&p=3fea39e73411819ebc7ec5b1761f5e2e",
        "3fea39e73411819ebc7ec5b1761f5e2e",
        "3FEA39E7-3411-819E-BC7E-C5B1761F5E2E",
        "  3fea39e7-3411-819e-bc7e-c5b1761f5e2e\n",
    ],
)
def test_parse_ref_accepts(arg):
    ref = notion.parse_ref(arg)
    assert ref.id == PAGE_ID
    assert ref.url == "https://app.notion.com/p/3fea39e73411819ebc7ec5b1761f5e2e"


@pytest.mark.parametrize(
    "arg",
    [
        "",
        "not a url",
        "3fea39e73411819ebc7ec5b1761f5e2",  # 31 hex
        "3fea39e73411819ebc7ec5b1761f5e2eff",  # too long
        "https://github.com/p/3fea39e73411819ebc7ec5b1761f5e2e",
        "https://app.notion.com/p/",
        "https://www.notion.so/Title-3fea39e7",
    ],
)
def test_parse_ref_rejects(arg):
    with pytest.raises(ValueError):
        notion.parse_ref(arg)


def test_resource_fields():
    page = {
        "object": "page",
        "properties": {
            "Title": {"type": "title", "title": [{"plain_text": "Intro to "}, {"plain_text": "tensor cores"}]},
            "URL": {"type": "url", "url": "https://example.com/post"},
            "Type": {"type": "select", "select": {"name": "article"}},
            "Topic": {"type": "multi_select", "multi_select": [{"name": "GPU kernels"}, {"name": "KV cache"}]},
            "Status": {"type": "status", "status": {"name": "Inbox"}},
        },
    }
    assert notion.resource_fields(page) == {
        "title": "Intro to tensor cores",
        "url": "https://example.com/post",
        "type": "article",
        "topics": ["GPU kernels", "KV cache"],
    }


def test_resource_fields_empty():
    page = {
        "object": "page",
        "properties": {
            "Title": {"type": "title", "title": []},
            "URL": {"type": "url", "url": None},
            "Type": {"type": "select", "select": None},
            "Topic": {"type": "multi_select", "multi_select": []},
        },
    }
    assert notion.resource_fields(page) == {"title": "", "url": None, "type": None, "topics": []}
