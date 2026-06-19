use std::path::{Component, Path, PathBuf};

use crate::error::AppError;

const GAME_DATA_REFUSAL: &str = "Refusing to write into a game Data directory; pack/extract into an MO2 mod overlay instead, or pass --allow-game-data to override.";

pub fn ensure_writable_target(path: &Path, allow_game_data: bool) -> Result<(), AppError> {
    if !allow_game_data && is_protected_game_path(path) {
        return Err(AppError::RefusedGameDataWrite(GAME_DATA_REFUSAL.into()));
    }

    Ok(())
}

pub fn is_protected_game_path(path: &Path) -> bool {
    let absolute = absolute_lexical(path);
    let segments: Vec<String> = absolute
        .components()
        .filter_map(|component| match component {
            Component::Normal(value) => Some(value.to_string_lossy().to_ascii_lowercase()),
            _ => None,
        })
        .collect();

    has_steam_game_data_chain(&segments) || has_stock_game_data_chain(&segments)
}

fn absolute_lexical(path: &Path) -> PathBuf {
    let candidate = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    };

    normalize_components(&candidate)
}

fn normalize_components(path: &Path) -> PathBuf {
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                normalized.pop();
            }
            _ => normalized.push(component.as_os_str()),
        }
    }
    normalized
}

fn has_steam_game_data_chain(segments: &[String]) -> bool {
    segments.windows(4).any(|window| {
        window[0] == "steamapps"
            && window[1] == "common"
            && !window[2].is_empty()
            && window[3] == "data"
    })
}

fn has_stock_game_data_chain(segments: &[String]) -> bool {
    segments.iter().enumerate().any(|(index, segment)| {
        segment == "stock game" && segments[index + 1..].iter().any(|later| later == "data")
    })
}
