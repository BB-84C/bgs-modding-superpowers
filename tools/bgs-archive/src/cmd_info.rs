use std::path::Path;

use ba2::{fo4, tes4};

use crate::{
    archive::{open_any, AnyArchive},
    error::AppError,
    model::{ArchiveInfo, Envelope},
};

pub fn run(archive: &Path, json: bool) -> Result<(), AppError> {
    let opened = open_any(archive)?;
    let entries = opened.entries();
    let info = ArchiveInfo {
        path: archive.display().to_string(),
        family: opened.family().to_string(),
        version: version(&opened),
        format: format(&opened).map(str::to_string),
        compression: compression(&opened).map(str::to_string),
        entry_count: entries.len(),
    };

    if json {
        println!("{}", serde_json::to_string(&Envelope::ok("info", info))?);
    } else {
        print_human(&info);
    }

    Ok(())
}

fn version(archive: &AnyArchive) -> Option<u32> {
    match archive {
        AnyArchive::Tes3(_) => None,
        AnyArchive::Tes4(_, meta) => Some(meta.version() as u32),
        AnyArchive::Fo4(_, meta) => Some(meta.version() as u32),
    }
}

fn format(archive: &AnyArchive) -> Option<&'static str> {
    match archive {
        AnyArchive::Fo4(_, meta) => Some(match meta.format() {
            fo4::Format::GNRL => "GNRL",
            fo4::Format::DX10 => "DX10",
            fo4::Format::GNMF => "GNMF",
        }),
        _ => None,
    }
}

fn compression(archive: &AnyArchive) -> Option<&'static str> {
    match archive {
        AnyArchive::Tes3(_) => None,
        AnyArchive::Tes4(_, meta) => Some(match meta.version() {
            tes4::Version::v103 | tes4::Version::v104 => "zlib",
            tes4::Version::v105 => "lz4",
        }),
        AnyArchive::Fo4(_, meta) => Some(match meta.compression_format() {
            fo4::CompressionFormat::Zip => "Zip",
            fo4::CompressionFormat::LZ4 => "LZ4",
        }),
    }
}

fn print_human(info: &ArchiveInfo) {
    println!("Archive: {}", info.path);
    println!("Family: {}", info.family);
    println!(
        "Version: {}",
        info.version
            .map(|value| value.to_string())
            .unwrap_or_else(|| "n/a".to_string())
    );
    println!("Format: {}", info.format.as_deref().unwrap_or("n/a"));
    println!(
        "Compression: {}",
        info.compression.as_deref().unwrap_or("n/a")
    );
    println!("Entries: {}", info.entry_count);
}
