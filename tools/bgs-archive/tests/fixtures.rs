use assert_cmd::Command;
use ba2::{
    fo4::{Archive, ArchiveKey, ArchiveOptions, Chunk, CompressionFormat, File, Format, Version},
    prelude::*,
};

#[test]
fn open_any_detects_fo4() {
    let tmp = tempfile::NamedTempFile::new().unwrap();
    let chunk = Chunk::from_decompressed(b"Hello world!\n");
    let file: File = [chunk].into_iter().collect();
    let key: ArchiveKey = b"hello.txt".into();
    let archive: Archive = [(key, file)].into_iter().collect();
    let options = ArchiveOptions::builder().strings(true).build();
    archive.write(&mut tmp.as_file(), &options).unwrap();

    let a = bgs_archive::archive::open_any(tmp.path()).unwrap();
    assert_eq!(a.family(), "fo4");
    let entries = a.entries();
    assert!(entries.iter().any(|e| e.path == "hello.txt"));
}

#[test]
fn open_any_uses_hash_path_when_fo4_strings_are_absent() {
    let tmp = tempfile::NamedTempFile::new().unwrap();
    let chunk = Chunk::from_decompressed(b"Hello world!\n");
    let file: File = [chunk].into_iter().collect();
    let key: ArchiveKey = b"hello.txt".into();
    let archive: Archive = [(key, file)].into_iter().collect();
    archive
        .write(&mut tmp.as_file(), &ArchiveOptions::default())
        .unwrap();

    let a = bgs_archive::archive::open_any(tmp.path()).unwrap();
    let entries = a.entries();

    assert_eq!(entries.len(), 1);
    assert!(entries[0].path.starts_with("<hash:"));
}

#[test]
fn info_json_reports_fo4_v2_metadata() {
    let tmp = tempfile::NamedTempFile::new().unwrap();
    let chunk = Chunk::from_decompressed(b"Hello world!\n");
    let file: File = [chunk].into_iter().collect();
    let key: ArchiveKey = b"hello.txt".into();
    let archive: Archive = [(key, file)].into_iter().collect();
    let options = ArchiveOptions::builder()
        .version(Version::v2)
        .format(Format::GNRL)
        .compression_format(CompressionFormat::Zip)
        .strings(true)
        .build();
    archive.write(&mut tmp.as_file(), &options).unwrap();

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(["info", tmp.path().to_str().unwrap(), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();

    let value: serde_json::Value = serde_json::from_slice(&output).unwrap();
    assert_eq!(value["data"]["family"], "fo4");
    assert_eq!(value["data"]["version"], 2);
}

#[test]
fn list_json_reports_entries_and_filter_matches_glob() {
    let tmp = tempfile::NamedTempFile::new().unwrap();
    let hello: File = [Chunk::from_decompressed(b"Hello world!\n")]
        .into_iter()
        .collect();
    let data: File = [Chunk::from_decompressed(&[0, 1, 2, 3])]
        .into_iter()
        .collect();
    let archive: Archive = [
        (ArchiveKey::from(&b"hello.txt"[..]), hello),
        (ArchiveKey::from(&b"data.bin"[..]), data),
    ]
    .into_iter()
    .collect();
    let options = ArchiveOptions::builder().strings(true).build();
    archive.write(&mut tmp.as_file(), &options).unwrap();

    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(["list", tmp.path().to_str().unwrap(), "--json"])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let value: serde_json::Value = serde_json::from_slice(&output).unwrap();
    assert_eq!(value["data"].as_array().unwrap().len(), 2);

    let filtered_output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "list",
            tmp.path().to_str().unwrap(),
            "--filter",
            "*.txt",
            "--json",
        ])
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let filtered: serde_json::Value = serde_json::from_slice(&filtered_output).unwrap();
    let entries = filtered["data"].as_array().unwrap();
    assert_eq!(entries.len(), 1);
    assert_eq!(entries[0]["path"], "hello.txt");
}

#[test]
fn extract_writes_fo4_entry_bytes_to_output_directory() {
    let tmp = tempfile::NamedTempFile::new().unwrap();
    let chunk = Chunk::from_decompressed(b"Hello world!\n");
    let file: File = [chunk].into_iter().collect();
    let key: ArchiveKey = b"hello.txt".into();
    let archive: Archive = [(key, file)].into_iter().collect();
    let options = ArchiveOptions::builder().strings(true).build();
    archive.write(&mut tmp.as_file(), &options).unwrap();

    let out_dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "extract",
            tmp.path().to_str().unwrap(),
            "--out",
            out_dir.path().to_str().unwrap(),
        ])
        .assert()
        .success();

    let extracted = std::fs::read(out_dir.path().join("hello.txt")).unwrap();
    assert_eq!(extracted, b"Hello world!\n");
}

#[test]
fn extract_skips_entries_that_would_traverse_outside_output_directory() {
    let root = tempfile::tempdir().unwrap();
    let archive_path = root.path().join("malicious.ba2");
    let chunk = Chunk::from_decompressed(b"owned\n");
    let file: File = [chunk].into_iter().collect();
    let key: ArchiveKey = b"../../evil.txt".as_slice().into();
    let archive: Archive = [(key, file)].into_iter().collect();
    let options = ArchiveOptions::builder().strings(true).build();
    let mut archive_file = std::fs::File::create(&archive_path).unwrap();
    archive.write(&mut archive_file, &options).unwrap();

    let out_dir = root.path().join("safe").join("extract");
    let archive = bgs_archive::archive::open_any(&archive_path).unwrap();
    let extracted = archive.extract(&out_dir, None, false).unwrap();

    assert!(extracted.is_empty());
    assert!(!root.path().join("evil.txt").exists());
    assert!(!root.path().join("safe").join("evil.txt").exists());
    assert!(!out_dir.join("evil.txt").exists());
}

#[test]
fn pack_fo4_round_trips_file_bytes_with_paths() {
    let input_dir = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(input_dir.path().join("sub")).unwrap();
    std::fs::write(input_dir.path().join("sub").join("a.txt"), b"alpha\n").unwrap();
    std::fs::write(input_dir.path().join("b.bin"), b"\x00\x01\x02beta").unwrap();

    let out_archive = tempfile::NamedTempFile::new().unwrap();
    Command::cargo_bin("bgs-archive")
        .unwrap()
        .args([
            "pack",
            input_dir.path().to_str().unwrap(),
            out_archive.path().to_str().unwrap(),
            "--game",
            "fallout4",
        ])
        .assert()
        .success();

    let extract_dir = tempfile::tempdir().unwrap();
    let archive = bgs_archive::archive::open_any(out_archive.path()).unwrap();
    let extracted = archive.extract(extract_dir.path(), None, false).unwrap();

    assert!(extracted.iter().any(|path| path == "sub/a.txt"));
    assert!(extracted.iter().any(|path| path == "b.bin"));
    assert_eq!(
        std::fs::read(extract_dir.path().join("sub").join("a.txt")).unwrap(),
        b"alpha\n"
    );
    assert_eq!(
        std::fs::read(extract_dir.path().join("b.bin")).unwrap(),
        b"\x00\x01\x02beta"
    );
}
