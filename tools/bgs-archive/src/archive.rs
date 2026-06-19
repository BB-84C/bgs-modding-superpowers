use std::{
    fs,
    fs::File,
    io::BufReader,
    path::{Component, Path, PathBuf},
};

use ba2::prelude::*;
use globset::Glob;

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

    /// Extract entries (optionally glob-filtered) under `out_dir`. Returns extracted virtual paths.
    pub fn extract(
        &self,
        out_dir: &Path,
        filter: Option<&str>,
        flatten: bool,
    ) -> Result<Vec<String>, crate::error::AppError> {
        let matcher = filter
            .map(|pattern| {
                Glob::new(pattern)
                    .map_err(|error| AppError::Unsupported(format!("invalid glob filter: {error}")))
                    .map(|glob| glob.compile_matcher())
            })
            .transpose()?;
        let mut extracted = Vec::new();

        match self {
            AnyArchive::Tes3(archive) => {
                for (key, file) in archive.iter() {
                    let virtual_path = name_or_tes3_hash(key);
                    if !matches_filter(&virtual_path, matcher.as_ref()) {
                        continue;
                    }

                    if let Some(mut dst) = create_output(out_dir, &virtual_path, flatten)? {
                        file.write(&mut dst)?;
                        extracted.push(virtual_path);
                    }
                }
            }
            AnyArchive::Tes4(archive, meta) => {
                let opts: ba2::tes4::FileCompressionOptions = meta.into();
                for (directory_key, directory) in archive.iter() {
                    for (file_key, file) in directory.iter() {
                        let virtual_path = join_tes4_path(directory_key, file_key);
                        if !matches_filter(&virtual_path, matcher.as_ref()) {
                            continue;
                        }

                        if let Some(mut dst) = create_output(out_dir, &virtual_path, flatten)? {
                            file.write(&mut dst, &opts)?;
                            extracted.push(virtual_path);
                        }
                    }
                }
            }
            AnyArchive::Fo4(archive, meta) => {
                let opts: ba2::fo4::FileWriteOptions = meta.into();
                for (key, file) in archive.iter() {
                    let virtual_path = name_or_fo4_hash(key);
                    if !matches_filter(&virtual_path, matcher.as_ref()) {
                        continue;
                    }

                    if let Some(mut dst) = create_output(out_dir, &virtual_path, flatten)? {
                        file.write(&mut dst, &opts)?;
                        extracted.push(virtual_path);
                    }
                }
            }
        }

        Ok(extracted)
    }
}

fn matches_filter(path: &str, matcher: Option<&globset::GlobMatcher>) -> bool {
    matcher.is_none_or(|matcher| matcher.is_match(path))
}

fn create_output(
    out_dir: &Path,
    virtual_path: &str,
    flatten: bool,
) -> Result<Option<File>, AppError> {
    if sanitize_entry_path(out_dir, virtual_path).is_none() {
        eprintln!("warning: skipped unsafe archive entry path: {virtual_path}");
        return Ok(None);
    }

    let output_path = if flatten {
        let file_name = virtual_path
            .replace('\\', "/")
            .rsplit('/')
            .find(|part| !part.is_empty())
            .map(str::to_string)
            .unwrap_or_else(|| virtual_path.to_string());
        sanitize_entry_path(out_dir, &file_name)
    } else {
        sanitize_entry_path(out_dir, virtual_path)
    };

    let Some(dest) = output_path else {
        eprintln!("warning: skipped unsafe archive entry path: {virtual_path}");
        return Ok(None);
    };

    if let Some(parent) = dest.parent() {
        fs::create_dir_all(parent)?;
    }
    Ok(Some(File::create(dest)?))
}

fn sanitize_entry_path(out_dir: &Path, raw: &str) -> Option<PathBuf> {
    let normalized = raw.replace('\\', "/");
    let raw_path = Path::new(&normalized);
    let mut relative = PathBuf::new();

    for component in raw_path.components() {
        match component {
            Component::Normal(part) => relative.push(part),
            Component::CurDir => {}
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => return None,
        }
    }

    if relative.as_os_str().is_empty() {
        return None;
    }

    let dest = out_dir.join(&relative);
    path_stays_under(out_dir, &dest).then_some(dest)
}

fn path_stays_under(base: &Path, candidate: &Path) -> bool {
    let base_components: Vec<_> = base.components().collect();
    let candidate_components: Vec<_> = candidate.components().collect();
    candidate_components.starts_with(&base_components)
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
