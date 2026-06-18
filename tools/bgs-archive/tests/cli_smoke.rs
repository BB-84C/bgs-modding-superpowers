use assert_cmd::Command;

#[test]
fn prints_version() {
    Command::cargo_bin("bgs-archive")
        .unwrap()
        .arg("--version")
        .assert()
        .success()
        .stdout(predicates::str::contains("bgs-archive"));
}
