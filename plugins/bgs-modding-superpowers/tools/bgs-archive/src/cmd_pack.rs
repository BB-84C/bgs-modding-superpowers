use std::{collections::BTreeMap, fs, path::Path};

use ba2::prelude::*;
use serde::Serialize;
use walkdir::WalkDir;

use crate::{
    error::AppError,
    game::{Compress, Family, Game, PackFormat},
    model::Envelope,
};

#[derive(Serialize)]
struct PackResult {
    out_archive: String,
    family: &'static str,
    version: Option<u32>,
    entry_count: usize,
}

struct PackEntry {
    rel_path: String,
    bytes: Vec<u8>,
}

pub struct PackRequest<'a> {
    pub input_dir: &'a Path,
    pub out_archive: &'a Path,
    pub game: Game,
    pub format: PackFormat,
    pub compress: Option<Compress>,
    pub strings: bool,
    pub allow_game_data: bool,
    pub json: bool,
}

pub fn run(request: PackRequest<'_>) -> Result<(), AppError> {
    crate::safety::ensure_writable_target(request.out_archive, request.allow_game_data)?;

    if request.format == PackFormat::Dx10 {
        return Err(AppError::Unsupported(
            "dx10_pack not yet supported (Task A-DX10)".into(),
        ));
    }

    let entries = collect_entries(request.input_dir)?;
    match request.game.family() {
        Family::Tes3 => write_tes3(&entries, request.out_archive)?,
        Family::Tes4 => write_tes4(&entries, request.out_archive, request.game)?,
        Family::Fo4 => write_fo4(
            &entries,
            request.out_archive,
            request.game,
            request.format,
            request.compress,
            request.strings,
        )?,
    }

    let result = PackResult {
        out_archive: request.out_archive.display().to_string(),
        family: family_name(request.game.family()),
        version: version(request.game),
        entry_count: entries.len(),
    };

    if request.json {
        println!("{}", serde_json::to_string(&Envelope::ok("pack", result))?);
    } else {
        print_human(&result);
    }

    Ok(())
}

fn collect_entries(input_dir: &Path) -> Result<Vec<PackEntry>, AppError> {
    let mut entries = Vec::new();

    for entry in WalkDir::new(input_dir) {
        let entry = entry.map_err(walkdir_error)?;
        if !entry.file_type().is_file() {
            continue;
        }

        let path = entry.path();
        let rel_path = path
            .strip_prefix(input_dir)
            .map_err(|error| AppError::Unsupported(format!("invalid input path: {error}")))?
            .to_string_lossy()
            .replace('\\', "/");
        entries.push(PackEntry {
            rel_path,
            bytes: fs::read(path)?,
        });
    }

    entries.sort_by(|left, right| left.rel_path.cmp(&right.rel_path));
    Ok(entries)
}

fn write_fo4(
    entries: &[PackEntry],
    out_archive: &Path,
    game: Game,
    format: PackFormat,
    compress: Option<Compress>,
    strings: bool,
) -> Result<(), AppError> {
    let version = game
        .fo4_version()
        .ok_or_else(|| AppError::Unsupported(format!("{:?} is not an fo4-family game", game)))?;
    let compression_format = compress
        .and_then(Compress::fo4_compression)
        .unwrap_or(ba2::fo4::CompressionFormat::Zip);
    let options = ba2::fo4::ArchiveOptions::builder()
        .format(format.fo4_format())
        .version(version)
        .compression_format(compression_format)
        .strings(strings)
        .build();
    let compression_options: ba2::fo4::ChunkCompressionOptions = (&options).into();

    let mut archive = ba2::fo4::Archive::default();
    for entry in entries {
        let chunk = ba2::fo4::Chunk::from_decompressed(entry.bytes.clone().into_boxed_slice());
        let chunk = match compress {
            Some(Compress::Zip | Compress::Lz4) => chunk.compress(&compression_options)?,
            Some(Compress::None) | None => chunk,
        };
        let file: ba2::fo4::File = [chunk].into_iter().collect();
        archive.insert(ba2::fo4::ArchiveKey::from(entry.rel_path.as_bytes()), file);
    }

    let mut out = create_output_file(out_archive)?;
    archive.write(&mut out, &options)?;
    Ok(())
}

fn write_tes4(entries: &[PackEntry], out_archive: &Path, game: Game) -> Result<(), AppError> {
    let version = game
        .tes4_version()
        .ok_or_else(|| AppError::Unsupported(format!("{:?} is not a tes4-family game", game)))?;
    let mut grouped: BTreeMap<String, Vec<(&str, ba2::tes4::File<'static>)>> = BTreeMap::new();
    let mut types = ba2::tes4::ArchiveTypes::empty();

    for entry in entries {
        types |= archive_type_for_path(&entry.rel_path);
        let (directory, file_name) = split_tes4_path(&entry.rel_path);
        let file = ba2::tes4::File::from_decompressed(entry.bytes.clone().into_boxed_slice());
        grouped
            .entry(directory)
            .or_default()
            .push((file_name, file));
    }

    if types.is_empty() {
        types = ba2::tes4::ArchiveTypes::MISC;
    }

    let mut archive = ba2::tes4::Archive::default();
    for (directory_name, files) in grouped {
        let directory: ba2::tes4::Directory = files
            .into_iter()
            .map(|(file_name, file)| (ba2::tes4::DirectoryKey::from(file_name.as_bytes()), file))
            .collect();
        archive.insert(
            ba2::tes4::ArchiveKey::from(directory_name.as_bytes()),
            directory,
        );
    }

    let options = ba2::tes4::ArchiveOptions::builder()
        .types(types)
        .version(version)
        .build();
    let mut out = create_output_file(out_archive)?;
    archive.write(&mut out, &options)?;
    Ok(())
}

fn write_tes3(entries: &[PackEntry], out_archive: &Path) -> Result<(), AppError> {
    let mut archive = ba2::tes3::Archive::default();
    for entry in entries {
        let file: ba2::tes3::File = entry.bytes.clone().into_boxed_slice().into();
        archive.insert(ba2::tes3::ArchiveKey::from(entry.rel_path.as_bytes()), file);
    }

    let mut out = create_output_file(out_archive)?;
    archive.write(&mut out)?;
    Ok(())
}

fn split_tes4_path(path: &str) -> (String, &str) {
    path.rsplit_once('/').map_or_else(
        || (String::new(), path),
        |(dir, file)| (dir.to_string(), file),
    )
}

fn archive_type_for_path(path: &str) -> ba2::tes4::ArchiveTypes {
    match path
        .rsplit('.')
        .next()
        .map(str::to_ascii_lowercase)
        .as_deref()
    {
        Some("nif") => ba2::tes4::ArchiveTypes::MESHES,
        Some("dds") => ba2::tes4::ArchiveTypes::TEXTURES,
        Some("swf" | "xml" | "html") => ba2::tes4::ArchiveTypes::MENUS,
        Some("wav" | "xwm" | "mp3" | "ogg") => ba2::tes4::ArchiveTypes::SOUNDS,
        Some("fuz" | "lip") => ba2::tes4::ArchiveTypes::VOICES,
        Some("fxp") => ba2::tes4::ArchiveTypes::SHADERS,
        Some("spt") => ba2::tes4::ArchiveTypes::TREES,
        Some("fnt") => ba2::tes4::ArchiveTypes::FONTS,
        // v1 falls back to MISC for unknown extensions. This preserves byte round-trips;
        // game-specific surfacing of uncommon meshes/textures may need richer type inference.
        _ => ba2::tes4::ArchiveTypes::MISC,
    }
}

fn create_output_file(path: &Path) -> Result<fs::File, AppError> {
    if let Some(parent) = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent)?;
    }
    Ok(fs::File::create(path)?)
}

fn walkdir_error(error: walkdir::Error) -> AppError {
    let message = error.to_string();
    error.into_io_error().map_or_else(
        || AppError::Unsupported(format!("walkdir error: {message}")),
        AppError::Io,
    )
}

fn family_name(family: Family) -> &'static str {
    match family {
        Family::Tes3 => "tes3",
        Family::Tes4 => "tes4",
        Family::Fo4 => "fo4",
    }
}

fn version(game: Game) -> Option<u32> {
    game.fo4_version()
        .map(|version| version as u32)
        .or_else(|| game.tes4_version().map(|version| version as u32))
}

fn print_human(result: &PackResult) {
    println!("Archive: {}", result.out_archive);
    println!("Family: {}", result.family);
    println!(
        "Version: {}",
        result
            .version
            .map(|value| value.to_string())
            .unwrap_or_else(|| "n/a".to_string())
    );
    println!("Entries: {}", result.entry_count);
}
