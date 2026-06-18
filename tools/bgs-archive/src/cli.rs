use std::path::PathBuf;

use clap::{Parser, Subcommand};

#[derive(Debug, Parser)]
#[command(name = "bgs-archive", version, about)]
pub struct Cli {
    #[arg(long, global = true)]
    pub json: bool,

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
        #[arg(long)]
        game: String,
        #[arg(long)]
        format: Option<String>,
        #[arg(long)]
        compress: Option<String>,
        #[arg(long)]
        strings: bool,
    },
    Capabilities,
}
