use serde::Serialize;

#[derive(Serialize)]
pub struct Envelope<T> {
    pub ok: bool,
    pub tool: &'static str,
    pub command: &'static str,
    pub data: Option<T>,
    pub error: Option<ErrEnvelope>,
}

#[derive(Serialize)]
pub struct ErrEnvelope {
    pub code: String,
    pub message: String,
}

impl<T: Serialize> Envelope<T> {
    pub fn ok(command: &'static str, data: T) -> Self {
        Self {
            ok: true,
            tool: "bgs-archive",
            command,
            data: Some(data),
            error: None,
        }
    }

    pub fn err(code: &str, message: &str, command: &'static str) -> Self {
        Self {
            ok: false,
            tool: "bgs-archive",
            command,
            data: None,
            error: Some(ErrEnvelope {
                code: code.into(),
                message: message.into(),
            }),
        }
    }
}

#[derive(Serialize)]
pub struct ArchiveInfo {
    pub path: String,
    pub family: String,
    pub version: Option<u32>,
    pub format: Option<String>,
    pub compression: Option<String>,
    pub entry_count: usize,
}

#[derive(Serialize)]
pub struct EntryInfo {
    pub path: String,
    pub size: u64,
    pub compressed: bool,
}
