use serde::Serialize;

use crate::{error::AppError, model::Envelope};

#[derive(Serialize)]
struct Capabilities {
    tool: &'static str,
    version: &'static str,
    ba2_version: &'static str,
    games: &'static [&'static str],
    subcommands: &'static [Subcommand],
    write_support: WriteSupport,
    read_support: ReadSupport,
}

#[derive(Serialize)]
struct Subcommand {
    name: &'static str,
    args: &'static [&'static str],
}

#[derive(Serialize)]
struct WriteSupport {
    tes3: bool,
    tes4: bool,
    fo4_gnrl: bool,
    dx10: bool,
    gnmf: bool,
}

#[derive(Serialize)]
struct ReadSupport {
    all_families: bool,
}

const GAMES: &[&str] = &[
    "morrowind",
    "oblivion",
    "fallout3",
    "falloutnv",
    "skyrimle",
    "skyrimse",
    "fallout4",
    "fallout4ng",
    "fallout76",
    "starfield",
];

const SUBCOMMANDS: &[Subcommand] = &[
    Subcommand {
        name: "info",
        args: &["<archive>"],
    },
    Subcommand {
        name: "list",
        args: &["<archive>", "--filter <glob>", "--long"],
    },
    Subcommand {
        name: "extract",
        args: &["<archive>", "--out <dir>", "--filter <glob>", "--flatten"],
    },
    Subcommand {
        name: "pack",
        args: &[
            "<input-dir>",
            "<out-archive>",
            "--game <game>",
            "--format <gnrl|dx10>",
            "--compress <zip|lz4|none>",
            "--strings <bool>",
        ],
    },
    Subcommand {
        name: "capabilities",
        args: &[],
    },
];

pub fn run(json: bool) -> Result<(), AppError> {
    let capabilities = descriptor();

    if json {
        println!(
            "{}",
            serde_json::to_string(&Envelope::ok("capabilities", capabilities))?
        );
    } else {
        print_human(&capabilities);
    }

    Ok(())
}

fn descriptor() -> Capabilities {
    Capabilities {
        tool: "bgs-archive",
        version: env!("CARGO_PKG_VERSION"),
        ba2_version: "3.0.1",
        games: GAMES,
        subcommands: SUBCOMMANDS,
        write_support: WriteSupport {
            tes3: true,
            tes4: true,
            fo4_gnrl: true,
            dx10: false,
            gnmf: false,
        },
        read_support: ReadSupport { all_families: true },
    }
}

fn print_human(capabilities: &Capabilities) {
    println!("Tool: {} {}", capabilities.tool, capabilities.version);
    println!("ba2 crate: {}", capabilities.ba2_version);
    println!("Games: {}", capabilities.games.join(", "));
    println!("Read support: all families");
    println!(
        "Write support: tes3={}, tes4={}, fo4_gnrl={}, dx10={}, gnmf={}",
        capabilities.write_support.tes3,
        capabilities.write_support.tes4,
        capabilities.write_support.fo4_gnrl,
        capabilities.write_support.dx10,
        capabilities.write_support.gnmf
    );
    println!("Subcommands:");
    for command in capabilities.subcommands {
        println!("  {} {}", command.name, command.args.join(" "));
    }
}
