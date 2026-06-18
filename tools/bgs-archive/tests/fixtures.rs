use ba2::{
    fo4::{Archive, ArchiveKey, ArchiveOptions, Chunk, File},
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
