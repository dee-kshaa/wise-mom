from run_evaluation import run, OUTPUT_COLUMNS


def test_run_evaluation_generates_required_schema(tmp_path):
    input_csv = tmp_path / "requests.csv"
    output_csv = tmp_path / "output.csv"

    input_csv.write_text(
        "request_id,purchase_name,purchase_amount,category,necessity,current_balance,preferred_minimum_balance\n"
        "1,Notebook,500,EDUCATION,essential,30000,10000\n",
        encoding="utf-8",
    )

    run(input_csv, output_csv)

    content = output_csv.read_text(encoding="utf-8").splitlines()
    assert output_csv.exists()
    assert content
    header = content[0].split(",")
    assert header == OUTPUT_COLUMNS
