use anyhow::Result;
use bgs_archive::cli::{Cli, Command};
use clap::Parser;

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Command::Info { .. } => println!("info not yet implemented (task A2)"),
        Command::List { .. } => println!("list not yet implemented (task A2)"),
        Command::Extract { .. } => println!("extract not yet implemented (task A4)"),
        Command::Pack { .. } => println!("pack not yet implemented (task A8)"),
        Command::Capabilities => println!("capabilities not yet implemented (task A3)"),
    }

    Ok(())
}
