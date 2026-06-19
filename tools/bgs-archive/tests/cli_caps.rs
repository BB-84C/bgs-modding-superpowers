use assert_cmd::Command;
use serde_json::Value;

#[test]
fn caps_json_reports_archive_capabilities() {
    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(["caps", "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let envelope: Value = serde_json::from_slice(&output).unwrap();
    let data = &envelope["data"];

    assert_eq!(data["ba2_version"], "3.0.1");
    assert!(data["games"]
        .as_array()
        .unwrap()
        .contains(&Value::from("starfield")));
    assert_eq!(data["write_support"]["dx10"], false);
}
