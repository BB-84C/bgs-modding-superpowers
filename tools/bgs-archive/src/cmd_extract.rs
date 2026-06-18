use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::{archive::open_any, error::AppError, model::Envelope};

#[derive(Serialize)]
struct ExtractResult {
    output_dir: String,
    extracted_count: usize,
    paths: Vec<String>,
}

pub fn run(
    archive: &Path,
    out: Option<&Path>,
    filter: Option<&str>,
    flatten: bool,
    json: bool,
) -> Result<(), AppError> {
    let output_dir = out
        .map(Path::to_path_buf)
        .unwrap_or_else(|| default_out_dir(archive));
    let opened = open_any(archive)?;
    let paths = opened.extract(&output_dir, filter, flatten)?;
    let result = ExtractResult {
        output_dir: output_dir.display().to_string(),
        extracted_count: paths.len(),
        paths,
    };

    if json {
        println!(
            "{}",
            serde_json::to_string(&Envelope::ok("extract", result))?
        );
    } else {
        print_human(&result);
    }

    Ok(())
}

fn default_out_dir(archive: &Path) -> PathBuf {
    archive
        .file_stem()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn print_human(result: &ExtractResult) {
    println!("Output: {}", result.output_dir);
    println!("Extracted: {}", result.extracted_count);
    for path in &result.paths {
        println!("{path}");
    }
}
