from shared.tools.knowledge import list_jurisdictions


def test_list_jurisdictions_includes_seattle():
    jurisdictions = list_jurisdictions()
    ids = {entry["id"] for entry in jurisdictions}

    assert "seattle_wa" in ids
