from advisor.scoring import WEIGHTS, combined_weights, evaluate


def test_weights_sum_to_100():
    for domain, table in WEIGHTS.items():
        assert sum(table.values()) == 100, domain


def test_combined_weights_rescaled():
    w = combined_weights(["fullstack", "cloud"])
    assert abs(sum(w.values()) - 100) < 0.1
    assert "cost" in w and "accessibility" not in w


def test_approval_rules():
    dims = combined_weights(["frontend"])
    good = {d: 90 for d in dims}
    assert evaluate(["frontend"], good, ["low"]).approved
    assert not evaluate(["frontend"], good, ["high"]).approved
    low_fit = dict(good, requirement_fit=80)
    assert not evaluate(["frontend"], low_fit, []).approved
    weak = dict(good, security=55)
    assert not evaluate(["frontend"], weak, []).approved
