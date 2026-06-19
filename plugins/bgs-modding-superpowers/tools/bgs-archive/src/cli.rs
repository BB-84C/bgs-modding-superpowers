use std::path::PathBuf;

use clap::{Parser, Subcommand};

#[derive(Debug, Parser)]
#[command(name = "bgs-archive", version, about)]
pub struct Cli {
    #[arg(long, global = true)]
    pub json: bool,

    #[arg(long, global = true)]
    pub allow_game_data: bool,

    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    Info {
        archive: PathBuf,
    },
    List {
        archive: PathBuf,
        #[arg(long)]
        filter: Option<String>,
        #[arg(long)]
        long: bool,
    },
    Extract {
        archive: PathBuf,
        #[arg(long)]
        out: Option<PathBuf>,
        #[arg(long)]
        filter: Option<String>,
        #[arg(long)]
        flatten: bool,
    },
    Pack {
        input_dir: PathBuf,
        out_archive: PathBuf,
        #[arg(long, value_enum)]
        game: crate::game::Game,
        #[arg(long, value_enum, default_value_t = crate::game::PackFormat::Gnrl)]
        format: crate::game::PackFormat,
        #[arg(long, value_enum)]
        compress: Option<crate::game::Compress>,
        #[arg(long, default_value_t = true, action = clap::ArgAction::Set)]
        strings: bool,
    },
    #[command(alias = "caps")]
    Capabilities,
}
