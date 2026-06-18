use clap::ValueEnum;

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum Game {
    Morrowind,
    Oblivion,
    Fallout3,
    Falloutnv,
    Skyrimle,
    Skyrimse,
    Fallout4,
    Fallout4ng,
    Fallout76,
    Starfield,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum PackFormat {
    Gnrl,
    Dx10,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum Compress {
    Zip,
    Lz4,
    None,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Family {
    Tes3,
    Tes4,
    Fo4,
}

impl Game {
    pub fn family(self) -> Family {
        match self {
            Game::Morrowind => Family::Tes3,
            Game::Oblivion
            | Game::Fallout3
            | Game::Falloutnv
            | Game::Skyrimle
            | Game::Skyrimse => Family::Tes4,
            Game::Fallout4 | Game::Fallout4ng | Game::Fallout76 | Game::Starfield => Family::Fo4,
        }
    }

    pub fn tes4_version(self) -> Option<ba2::tes4::Version> {
        match self {
            Game::Oblivion => Some(ba2::tes4::Version::TES4),
            Game::Fallout3 => Some(ba2::tes4::Version::FO3),
            Game::Falloutnv => Some(ba2::tes4::Version::FNV),
            Game::Skyrimle => Some(ba2::tes4::Version::TES5),
            Game::Skyrimse => Some(ba2::tes4::Version::SSE),
            _ => None,
        }
    }

    pub fn fo4_version(self) -> Option<ba2::fo4::Version> {
        match self {
            Game::Fallout4 => Some(ba2::fo4::Version::v1),
            Game::Fallout4ng => Some(ba2::fo4::Version::v7),
            Game::Fallout76 => Some(ba2::fo4::Version::v1),
            Game::Starfield => Some(ba2::fo4::Version::v2),
            _ => None,
        }
    }
}

impl PackFormat {
    pub fn fo4_format(self) -> ba2::fo4::Format {
        match self {
            PackFormat::Gnrl => ba2::fo4::Format::GNRL,
            PackFormat::Dx10 => ba2::fo4::Format::DX10,
        }
    }
}

impl Compress {
    pub fn fo4_compression(self) -> Option<ba2::fo4::CompressionFormat> {
        match self {
            Compress::Zip => Some(ba2::fo4::CompressionFormat::Zip),
            Compress::Lz4 => Some(ba2::fo4::CompressionFormat::LZ4),
            Compress::None => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starfield_maps_to_fo4_v2() {
        assert_eq!(Game::Starfield.family(), Family::Fo4);
        assert_eq!(Game::Starfield.fo4_version(), Some(ba2::fo4::Version::v2));
    }

    #[test]
    fn skyrimse_maps_to_tes4_v105() {
        assert_eq!(Game::Skyrimse.family(), Family::Tes4);
        assert_eq!(
            Game::Skyrimse.tes4_version(),
            Some(ba2::tes4::Version::v105)
        );
    }

    #[test]
    fn fallout4ng_is_v7() {
        assert_eq!(Game::Fallout4ng.fo4_version(), Some(ba2::fo4::Version::v7));
    }

    #[test]
    fn morrowind_is_tes3_no_versions() {
        assert_eq!(Game::Morrowind.family(), Family::Tes3);
        assert_eq!(Game::Morrowind.tes4_version(), None);
        assert_eq!(Game::Morrowind.fo4_version(), None);
    }
}
