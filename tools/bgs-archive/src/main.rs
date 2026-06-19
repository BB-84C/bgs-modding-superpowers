use bgs_archive::cli::{Cli, Command};
use clap::Parser;

fn main() {
    let cli = Cli::parse();

    let result = match cli.command {
        Command::Info { archive } => bgs_archive::cmd_info::run(&archive, cli.json),
        Command::List {
            archive,
            filter,
            long,
        } => bgs_archive::cmd_list::run(&archive, filter.as_deref(), long, cli.json),
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
            cli.allow_game_data,
            cli.json,
        ),
        Command::Pack {
            input_dir,
            out_archive,
            game,
            format,
            compress,
            strings,
        } => bgs_archive::cmd_pack::run(bgs_archive::cmd_pack::PackRequest {
            input_dir: &input_dir,
            out_archive: &out_archive,
            game,
            format,
            compress,
            strings,
            allow_game_data: cli.allow_game_data,
            json: cli.json,
        }),
        Command::Capabilities => bgs_archive::cmd_caps::run(cli.json),
    };

    if let Err(error) = result {
        bgs_archive::error::emit(&error, cli.json);
        std::process::exit(1);
    }
}
