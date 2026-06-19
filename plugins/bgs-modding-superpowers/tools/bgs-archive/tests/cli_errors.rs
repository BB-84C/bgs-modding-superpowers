use std::{fs, path::Path};

use assert_cmd::Command;
use ba2::{
    fo4::{Archive, ArchiveKey, ArchiveOptions, Chunk, File},
    prelude::*,
};
use serde_json::Value;

#[test]
fn json_pack_error_is_stdout_envelope() {
    let temp = tempfile::tempdir().unwrap();
    let input_dir = temp.path().join("input");
    fs::create_dir_all(&input_dir).unwrap();
    fs::write(input_dir.join("a.txt"), b"alpha\n").unwrap();
    let out_archive = temp.path().join("out.ba2");

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "pack",
            path_str(&input_dir),
            path_str(&out_archive),
            "--game",
            "fallout4",
            "--format",
            "dx10",
            "--json",
        ])
        .assert()
        .failure()
        .code(1)
        .get_output()
        .clone();

    assert!(output.stderr.is_empty(), "stderr: {:?}", output.stderr);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["ok"], false);
    assert_eq!(value["error"]["code"], "unsupported");
}

#[test]
fn json_info_error_is_stdout_envelope() {
    let temp = tempfile::tempdir().unwrap();
    let missing = temp.path().join("missing.ba2");

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(["info", path_str(&missing), "--json"])
        .assert()
        .failure()
        .code(1)
        .get_output()
        .clone();

    assert!(output.stderr.is_empty(), "stderr: {:?}", output.stderr);
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["ok"], false);
    assert_eq!(value["error"]["code"], "io_error");
}

#[test]
fn extract_refuses_game_data_output_without_override() {
    let temp = tempfile::tempdir().unwrap();
    let archive = write_fo4_archive(temp.path(), "safe.txt");
    let game_data_out = temp
        .path()
        .join("steamapps")
        .join("common")
        .join("Synthetic Game")
        .join("Data")
        .join("extract");

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "extract",
            path_str(&archive),
            "--out",
            path_str(&game_data_out),
            "--json",
        ])
        .assert()
        .failure()
        .code(1)
        .get_output()
        .clone();

    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["ok"], false);
    assert_eq!(value["error"]["code"], "refused_game_data_write");
}

#[test]
fn pack_refuses_game_data_output_before_format_validation() {
    let temp = tempfile::tempdir().unwrap();
    let input_dir = temp.path().join("input");
    fs::create_dir_all(&input_dir).unwrap();
    fs::write(input_dir.join("a.txt"), b"alpha\n").unwrap();
    let game_data_archive = temp
        .path()
        .join("steamapps")
        .join("common")
        .join("Synthetic Game")
        .join("Data")
        .join("out.ba2");

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "pack",
            path_str(&input_dir),
            path_str(&game_data_archive),
            "--game",
            "fallout4",
            "--format",
            "dx10",
            "--json",
        ])
        .assert()
        .failure()
        .code(1)
        .get_output()
        .clone();

    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["ok"], false);
    assert_eq!(value["error"]["code"], "refused_game_data_write");
}

#[test]
fn extract_allow_game_data_override_does_not_refuse() {
    let temp = tempfile::tempdir().unwrap();
    let archive = write_fo4_archive(temp.path(), "safe.txt");
    let game_data_out = temp
        .path()
        .join("steamapps")
        .join("common")
        .join("Synthetic Game")
        .join("Data")
        .join("extract");

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "extract",
            path_str(&archive),
            "--out",
            path_str(&game_data_out),
            "--allow-game-data",
            "--json",
        ])
        .assert()
        .get_output()
        .clone();

    if output.status.success() {
        return;
    }

    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_ne!(value["error"]["code"], "refused_game_data_write");
}

fn write_fo4_archive(root: &Path, name: &str) -> std::path::PathBuf {
    let archive_path = root.join("input.ba2");
    let chunk = Chunk::from_decompressed(b"Hello world!\n");
    let file: File = [chunk].into_iter().collect();
    let key: ArchiveKey = name.as_bytes().into();
    let archive: Archive = [(key, file)].into_iter().collect();
    let options = ArchiveOptions::builder().strings(true).build();
    let mut out = fs::File::create(&archive_path).unwrap();
    archive.write(&mut out, &options).unwrap();
    archive_path
}

fn path_str(path: &Path) -> &str {
    path.to_str().unwrap()
}
