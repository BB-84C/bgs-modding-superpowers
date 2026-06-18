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
        Command::Pack {
            input_dir,
            out_archive,
            game,
            format,
            compress,
            strings,
        } => bgs_archive::cmd_pack::run(
            &input_dir,
            &out_archive,
            game,
            format,
            compress,
            strings,
            cli.json,
        )?,
        Command::Capabilities => println!("capabilities not yet implemented (task A3)"),
    }

    Ok(())
}
