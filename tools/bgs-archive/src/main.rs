use anyhow::Result;
use bgs_archive::cli::{Cli, Command};
use clap::Parser;

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Command::Info { archive } => bgs_archive::cmd_info::run(&archive, cli.json)?,
        Command::List {
            archive,
            filter,
            long,
        } => bgs_archive::cmd_list::run(&archive, filter.as_deref(), long, cli.json)?,
        Command::Extract {
            archive,
            out,
            filter,
            flatten,
        } => bgs_archive::cmd_extract::run(
            &archive,
            out.as_deref(),
            filter.as_deref(),
            flatten,
            cli.json,
        )?,
        Command::Pack { .. } => println!("pack not yet implemented (task A8)"),
        Command::Capabilities => println!("capabilities not yet implemented (task A3)"),
    }

    Ok(())
}
