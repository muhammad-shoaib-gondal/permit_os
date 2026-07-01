from api.services.project_service import _build_manhattan_rule_library


def test_manhattan_rule_library_is_large():
    rules = _build_manhattan_rule_library()
    assert len(rules) > 150


def test_manhattan_rule_library_area_filter_keeps_general_and_area_rules():
    all_rules = _build_manhattan_rule_library()
    rm_rules = _build_manhattan_rule_library(area="RM", project_type="multifamily_residential")

    assert len(rm_rules) > 40
    assert len(rm_rules) < len(all_rules)
    assert any("RM" in rule["rule"] for rule in rm_rules)
