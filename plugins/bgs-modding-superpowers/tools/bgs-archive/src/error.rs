use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("tes3 archive error: {0}")]
    Tes3(#[from] ba2::tes3::Error),
    #[error("tes4 archive error: {0}")]
    Tes4(#[from] ba2::tes4::Error),
    #[error("fo4 archive error: {0}")]
    Fo4(#[from] ba2::fo4::Error),
    #[error("unsupported: {0}")]
    Unsupported(String),
    #[error("not found: {0}")]
    NotFound(String),
    #[error("{0}")]
    RefusedGameDataWrite(String),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
}

impl AppError {
    pub fn code(&self) -> &'static str {
        match self {
            AppError::Io(_) => "io_error",
            AppError::Tes3(_) | AppError::Tes4(_) | AppError::Fo4(_) => "archive_error",
            AppError::Unsupported(_) => "unsupported",
            AppError::NotFound(_) => "not_found",
            AppError::RefusedGameDataWrite(_) => "refused_game_data_write",
            AppError::Json(_) => "json_error",
        }
    }
}

pub fn emit(e: &AppError, json: bool) {
    if json {
        let env = crate::model::Envelope::<()>::err(e.code(), &e.to_string(), "");
        println!("{}", serde_json::to_string(&env).unwrap());
    } else {
        eprintln!("error [{}]: {}", e.code(), e);
    }
}
