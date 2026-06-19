use std::{fs, path::Path};

use assert_cmd::Command;
use serde_json::Value;

const NIF_BYTES: &[u8] = b"NIFDATA\x00\x01";
const README_BYTES: &[u8] = b"hello roundtrip\n";

#[test]
fn pack_list_extract_round_trips_cross_game_archives() {
    for (game, extension) in [
        ("starfield", "ba2"),
        ("skyrimse", "bsa"),
        ("fallout4", "ba2"),
    ] {
        round_trip(game, extension);
    }
}

fn round_trip(game: &str, extension: &str) {
    let temp = tempfile::tempdir().unwrap();
    let input_dir = temp.path().join("input");
    let meshes_dir = input_dir.join("meshes");
    fs::create_dir_all(&meshes_dir).unwrap();
    fs::write(meshes_dir.join("test.nif"), NIF_BYTES).unwrap();
    fs::write(input_dir.join("readme.txt"), README_BYTES).unwrap();

    let archive = temp.path().join(format!("roundtrip-{game}.{extension}"));
    Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "pack",
            path_str(&input_dir),
            path_str(&archive),
            "--game",
            game,
        ])
        .assert()
        .success();

    let list_output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(["list", path_str(&archive), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let envelope: Value = serde_json::from_slice(&list_output).unwrap();
    let paths: Vec<&str> = envelope["data"]
        .as_array()
        .unwrap()
        .iter()
        .map(|entry| entry["path"].as_str().unwrap())
        .collect();
    assert!(paths.contains(&"meshes/test.nif"), "{game} paths: {paths:?}");
    assert!(paths.contains(&"readme.txt"), "{game} paths: {paths:?}");

    let extract_dir = temp.path().join("extract");
    Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(["extract", path_str(&archive), "--out", path_str(&extract_dir)])
        .assert()
        .success();

    assert_eq!(fs::read(extract_dir.join("meshes/test.nif")).unwrap(), NIF_BYTES);
    assert_eq!(fs::read(extract_dir.join("readme.txt")).unwrap(), README_BYTES);
}

fn path_str(path: &Path) -> &str {
    path.to_str().unwrap()
}
