use std::path::Path;

use globset::Glob;

use crate::{
    archive::open_any,
    error::AppError,
    model::{EntryInfo, Envelope},
};

pub fn run(
    archive: &Path,
    filter: Option<&str>,
    long: bool,
    json: bool,
) -> Result<(), AppError> {
    let opened = open_any(archive)?;
    let mut entries = opened.entries();

    if let Some(pattern) = filter {
        let matcher = Glob::new(pattern)
            .map_err(|error| AppError::Unsupported(format!("invalid glob filter: {error}")))?
            .compile_matcher();
        entries.retain(|entry| matcher.is_match(&entry.path));
    }

    if json {
        println!("{}", serde_json::to_string(&Envelope::ok("list", entries))?);
    } else {
        print_human(&entries, long);
    }

    Ok(())
}

fn print_human(entries: &[EntryInfo], long: bool) {
    if long {
        println!("{:<12} {:<10} Path", "Size", "Compressed");
        for entry in entries {
            println!("{:<12} {:<10} {}", entry.size, entry.compressed, entry.path);
        }
    } else {
        for entry in entries {
            println!("{}", entry.path);
        }
    }
}
