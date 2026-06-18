use std::{fs::File, io::BufReader, path::Path};

use ba2::prelude::*;

use crate::{error::AppError, model::EntryInfo};

pub enum AnyArchive {
    Tes3(ba2::tes3::Archive<'static>),
    Tes4(ba2::tes4::Archive<'static>, ba2::tes4::ArchiveOptions),
    Fo4(ba2::fo4::Archive<'static>, ba2::fo4::ArchiveOptions),
}

pub fn open_any(path: &Path) -> Result<AnyArchive, AppError> {
    let file = File::open(path)?;
    let mut reader = BufReader::new(file);
    let format = ba2::guess_format(&mut reader)
        .ok_or_else(|| AppError::Unsupported("unrecognized archive format".into()))?;

    match format {
        ba2::FileFormat::TES3 => Ok(AnyArchive::Tes3(ba2::tes3::Archive::read(path)?)),
        ba2::FileFormat::TES4 => {
            let (archive, options) = ba2::tes4::Archive::read(path)?;
            Ok(AnyArchive::Tes4(archive, options))
        }
        ba2::FileFormat::FO4 => {
            let (archive, options) = ba2::fo4::Archive::read(path)?;
            Ok(AnyArchive::Fo4(archive, options))
        }
    }
}

impl AnyArchive {
    pub fn family(&self) -> &'static str {
        match self {
            AnyArchive::Tes3(_) => "tes3",
            AnyArchive::Tes4(_, _) => "tes4",
            AnyArchive::Fo4(_, _) => "fo4",
        }
    }

    pub fn entries(&self) -> Vec<EntryInfo> {
        match self {
            AnyArchive::Tes3(archive) => archive
                .iter()
                .map(|(key, file)| EntryInfo {
                    path: name_or_tes3_hash(key),
                    size: usize_to_u64(file.len()),
                    compressed: false,
                })
                .collect(),
            AnyArchive::Tes4(archive, _) => archive
                .iter()
                .flat_map(|(directory_key, directory)| {
                    directory.iter().map(move |(file_key, file)| EntryInfo {
                        path: join_tes4_path(directory_key, file_key),
                        size: usize_to_u64(file.len()),
                        compressed: file.is_compressed(),
                    })
                })
                .collect(),
            AnyArchive::Fo4(archive, _) => archive
                .iter()
                .map(|(key, file)| EntryInfo {
                    path: name_or_fo4_hash(key),
                    size: usize_to_u64(file.iter().map(|chunk| chunk.len()).sum()),
                    compressed: file.iter().any(|chunk| chunk.is_compressed()),
                })
                .collect(),
        }
    }
}

fn bstr_path(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).replace('\\', "/")
}

fn name_or_tes3_hash(key: &ba2::tes3::ArchiveKey<'_>) -> String {
    let name = key.name();
    if name.is_empty() {
        format!("<hash:{:016x}>", key.hash().numeric())
    } else {
        bstr_path(name)
    }
}

fn name_or_tes4_hash(prefix: &str, key: &ba2::tes4::DirectoryKey<'_>) -> String {
    let name = key.name();
    if name.is_empty() {
        format!("{prefix}<hash:{:016x}>", key.hash().numeric())
    } else {
        format!("{prefix}{}", bstr_path(name))
    }
}

fn name_or_fo4_hash(key: &ba2::fo4::ArchiveKey<'_>) -> String {
    let name = key.name();
    if name.is_empty() {
        let hash = key.hash();
        format!(
            "<hash:{:08x}-{:08x}-{:08x}>",
            hash.file, hash.extension, hash.directory
        )
    } else {
        bstr_path(name)
    }
}

fn join_tes4_path(
    directory_key: &ba2::tes4::ArchiveKey<'_>,
    file_key: &ba2::tes4::DirectoryKey<'_>,
) -> String {
    let directory = directory_key.name();
    let file_prefix = if directory.is_empty() {
        if directory_key.hash().numeric() == 0 {
            String::new()
        } else {
            format!("<dir-hash:{:016x}>/", directory_key.hash().numeric())
        }
    } else {
        let normalized = bstr_path(directory);
        let trimmed = normalized.trim_matches('/');
        if trimmed.is_empty() || trimmed == "." {
            String::new()
        } else {
            format!("{trimmed}/")
        }
    };

    name_or_tes4_hash(&file_prefix, file_key)
}

fn usize_to_u64(value: usize) -> u64 {
    value.try_into().unwrap_or(u64::MAX)
}
