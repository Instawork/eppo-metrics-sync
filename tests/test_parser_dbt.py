from eppo_metrics_sync.helper import load_yaml
from eppo_metrics_sync.eppo_metrics_sync import EppoMetricsSync, DbtModelParser

test_yaml_dir = "tests/yaml/dbt/"


# test that the package doesn't create invalid sql when things are missing
def test_valid_sql_missing_property():
    eppo_metrics_sync = EppoMetricsSync(
        directory=None, dbt_model_prefix="foo"
    )

    eppo_metrics_sync.load_dbt_yaml(path=test_yaml_dir + "valid/null_row_schema.yml")
    yaml = load_yaml(test_yaml_dir + "valid/null_row_schema.yml")
    model = yaml.get("models")[0]

    parser = DbtModelParser(model, "foo")
    parser.parse_columns()
    parser.format()
    sql = parser.eppo_fact_source.get("sql")
    print(sql)

    assert (
        sql
        == "SELECT\n    NULL AS gross_revenue,\n    NULL AS timestamp\nFROM\n    foo"
    )


def test_parse_fact_name():
    eppo_metrics_sync = EppoMetricsSync(
        directory=None, dbt_model_prefix="foo"
    )

    eppo_metrics_sync.load_dbt_yaml(path=test_yaml_dir + "valid/name_via_tag.yml")
    yaml = load_yaml(test_yaml_dir + "valid/name_via_tag.yml")
    model = yaml.get("models")[0]

    parser = DbtModelParser(model, "foo")
    parser.parse_columns()
    assert parser.eppo_facts == [
        {
            "name": "Is From Ad Campaign",
            "column": "is_from_ad_campaign",
            "description": "Whether the revenue was generated from an ad campaign",
            "desired_change": "increase",
        }
    ]
