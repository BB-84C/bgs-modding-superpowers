use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
};

use assert_cmd::Command;
use serde_json::Value;
use sha2::{Digest, Sha256};

const FO4_BA2: &str = r"D:\awesome-bgs-mod-master\.opencode\artifacts\archive-papyrus-tools\fixtures\fo4-ba2\ccbgsfo4008-pipgrn - main.ba2";
const SKYRIM_BSA: &str = r"D:\awesome-bgs-mod-master\.opencode\artifacts\archive-papyrus-tools\fixtures\skyrim-bsa\SofiaHideTrackingMarker.bsa";

#[test]
#[ignore = "Task A11 uses staged real archives; run explicitly on machines with fixtures"]
fn real_archive_structural_and_self_consistency_acceptance_cli_only() {
    let repo_root = repo_root();
    let acceptance_dir = repo_root.join(".opencode/artifacts/archive-papyrus-tools/acceptance");
    let work_dir = acceptance_dir.join("A11-rust-work");
    let evidence_path = acceptance_dir.join("A11-real-archive-acceptance-rust.md");
    reset_dir(&work_dir);
    fs::create_dir_all(&acceptance_dir).unwrap();

    let fixtures = [
        Fixture {
            name: "FO4 BA2",
            path: PathBuf::from(FO4_BA2),
            expected_family: "fo4",
            expected_version: 1,
            game: "fallout4",
            repacked_name: "fo4-repacked.ba2",
        },
        Fixture {
            name: "Skyrim SE BSA",
            path: PathBuf::from(SKYRIM_BSA),
            expected_family: "tes4",
            expected_version: 105,
            game: "skyrimse",
            repacked_name: "skyrim-repacked.bsa",
        },
    ];

    let mut evidence = Evidence::new();
    let mut all_passed = true;

    for fixture in fixtures {
        let result = run_fixture(&fixture, &work_dir);
        all_passed &= result.passed();
        evidence.push_fixture(&fixture, &result);
    }

    evidence.write(&evidence_path);
    println!("A11 CLI-only evidence: {}", evidence_path.display());

    assert!(
        all_passed,
        "A11 real archive acceptance failed; see {}",
        evidence_path.display()
    );
}

struct Fixture {
    name: &'static str,
    path: PathBuf,
    expected_family: &'static str,
    expected_version: u64,
    game: &'static str,
    repacked_name: &'static str,
}

struct FixtureResult {
    info_json: String,
    list_json: String,
    info_ok: bool,
    structural_rows: Vec<StructuralRow>,
    round_trip_rows: Vec<HashRow>,
    missing_after_round_trip: Vec<String>,
    extra_after_round_trip: Vec<String>,
}

impl FixtureResult {
    fn passed(&self) -> bool {
        self.info_ok
            && !self.structural_rows.is_empty()
            && self.structural_rows.iter().all(|row| row.verdict)
            && !self.round_trip_rows.is_empty()
            && self.round_trip_rows.iter().all(|row| row.matches)
            && self.missing_after_round_trip.is_empty()
            && self.extra_after_round_trip.is_empty()
    }
}

struct ListEntry {
    path: String,
    size: u64,
}

struct StructuralRow {
    path: String,
    extension: String,
    expected_magic: String,
    actual_magic: String,
    size_reported: u64,
    size_extracted: u64,
    size_match: bool,
    verdict: bool,
}

#[derive(Clone)]
struct HashRow {
    path: String,
    original_sha256: String,
    round_trip_sha256: String,
    matches: bool,
    first_diff_offset: Option<usize>,
}

fn run_fixture(fixture: &Fixture, work_dir: &Path) -> FixtureResult {
    assert!(
        fixture.path.exists(),
        "fixture missing: {}",
        fixture.path.display()
    );
    let safe_name = fixture.name.to_ascii_lowercase().replace([' ', '/'], "_");
    let out_dir = work_dir.join(format!("{safe_name}_extract"));
    let repacked = work_dir.join(fixture.repacked_name);
    let reout_dir = work_dir.join(format!("{safe_name}_reout"));

    let info_json = run_cli(["info", path_str(&fixture.path), "--json"]);
    let list_json = run_cli(["list", path_str(&fixture.path), "--json"]);
    let info: Value = serde_json::from_str(&info_json).unwrap();
    let info_ok = info["ok"].as_bool() == Some(true)
        && info["data"]["family"].as_str() == Some(fixture.expected_family)
        && info["data"]["version"].as_u64() == Some(fixture.expected_version);
    let entries = parse_list(&list_json);

    reset_dir(&out_dir);
    run_cli([
        "extract",
        path_str(&fixture.path),
        "--out",
        path_str(&out_dir),
    ]);
    let structural_rows = entries
        .iter()
        .map(|entry| validate_entry(entry, &out_dir))
        .collect::<Vec<_>>();

    run_cli([
        "pack",
        path_str(&out_dir),
        path_str(&repacked),
        "--game",
        fixture.game,
    ]);
    reset_dir(&reout_dir);
    run_cli([
        "extract",
        path_str(&repacked),
        "--out",
        path_str(&reout_dir),
    ]);
    let comparison = compare_trees(&out_dir, &reout_dir);

    FixtureResult {
        info_json,
        list_json,
        info_ok,
        structural_rows,
        round_trip_rows: comparison.rows,
        missing_after_round_trip: comparison.only_left,
        extra_after_round_trip: comparison.only_right,
    }
}

fn run_cli<const N: usize>(args: [&str; N]) -> String {
    let output = Command::cargo_bin("bgs-archive")
        .unwrap()
        .args(args)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    String::from_utf8(output).unwrap()
}

fn parse_list(list_json: &str) -> Vec<ListEntry> {
    let value: Value = serde_json::from_str(list_json).unwrap();
    value["data"]
        .as_array()
        .unwrap()
        .iter()
        .map(|entry| ListEntry {
            path: entry["path"].as_str().unwrap().to_string(),
            size: entry["size"].as_u64().unwrap(),
        })
        .collect()
}

fn validate_entry(entry: &ListEntry, out_dir: &Path) -> StructuralRow {
    let file_path = out_dir.join(entry.path.replace('/', "\\"));
    let bytes =
        fs::read(&file_path).unwrap_or_else(|error| panic!("{}: {error}", file_path.display()));
    let extension = file_path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let size_extracted = bytes.len() as u64;
    let size_match = size_extracted == entry.size;
    let (expected_magic, magic_ok) = expected_magic(&extension, &bytes);
    StructuralRow {
        path: entry.path.clone(),
        extension,
        expected_magic,
        actual_magic: magic_summary(&bytes),
        size_reported: entry.size,
        size_extracted,
        size_match,
        verdict: size_match && magic_ok && !bytes.is_empty(),
    }
}

fn expected_magic(extension: &str, bytes: &[u8]) -> (String, bool) {
    match extension {
        "dds" => ("DDS ".into(), bytes.starts_with(b"DDS ")),
        "nif" => (
            "Gamebryo File Format or NetImmerse".into(),
            bytes.starts_with(b"Gamebryo File Format") || bytes.starts_with(b"NetImmerse"),
        ),
        "pex" => (
            "FA 57 C0 DE".into(),
            bytes.starts_with(&[0xFA, 0x57, 0xC0, 0xDE]),
        ),
        "bgsm" => ("BGSM".into(), bytes.starts_with(b"BGSM")),
        "bgem" => ("BGEM".into(), bytes.starts_with(b"BGEM")),
        "wav" | "xwm" => ("RIFF".into(), bytes.starts_with(b"RIFF")),
        "fuz" => (
            "RIFF or FUZE".into(),
            bytes.starts_with(b"RIFF") || bytes.starts_with(b"FUZE"),
        ),
        "swf" => (
            "FWS or CWS".into(),
            bytes.starts_with(b"FWS") || bytes.starts_with(b"CWS"),
        ),
        _ => ("unknown extension; non-empty".into(), !bytes.is_empty()),
    }
}

fn magic_summary(bytes: &[u8]) -> String {
    let head = &bytes[..bytes.len().min(16)];
    let hex = head
        .iter()
        .map(|byte| format!("{byte:02X}"))
        .collect::<Vec<_>>()
        .join(" ");
    let ascii = head
        .iter()
        .map(|byte| {
            if byte.is_ascii_graphic() || *byte == b' ' {
                *byte as char
            } else {
                '.'
            }
        })
        .collect::<String>();
    format!("{hex} / {ascii}")
}

struct TreeComparison {
    rows: Vec<HashRow>,
    only_left: Vec<String>,
    only_right: Vec<String>,
}

fn compare_trees(left_root: &Path, right_root: &Path) -> TreeComparison {
    let left = collect_files(left_root);
    let right = collect_files(right_root);
    let mut rows = Vec::new();
    let mut only_left = Vec::new();
    let mut only_right = Vec::new();

    for (path, left_path) in &left {
        match right.get(path) {
            Some(right_path) => {
                let left_bytes = fs::read(left_path).unwrap();
                let right_bytes = fs::read(right_path).unwrap();
                let matches = left_bytes == right_bytes;
                rows.push(HashRow {
                    path: path.clone(),
                    original_sha256: sha256_hex(&left_bytes),
                    round_trip_sha256: sha256_hex(&right_bytes),
                    matches,
                    first_diff_offset: (!matches)
                        .then(|| first_diff_offset(&left_bytes, &right_bytes)),
                });
            }
            None => only_left.push(path.clone()),
        }
    }

    for path in right.keys() {
        if !left.contains_key(path) {
            only_right.push(path.clone());
        }
    }

    rows.sort_by(|left, right| left.path.cmp(&right.path));
    TreeComparison {
        rows,
        only_left,
        only_right,
    }
}

fn collect_files(root: &Path) -> BTreeMap<String, PathBuf> {
    let mut files = BTreeMap::new();
    collect_files_inner(root, root, &mut files);
    files
}

fn collect_files_inner(root: &Path, current: &Path, files: &mut BTreeMap<String, PathBuf>) {
    for entry in fs::read_dir(current).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        if entry.file_type().unwrap().is_dir() {
            collect_files_inner(root, &path, files);
        } else if entry.file_type().unwrap().is_file() {
            let rel = path
                .strip_prefix(root)
                .unwrap()
                .to_string_lossy()
                .replace('\\', "/");
            files.insert(rel.to_ascii_lowercase(), path);
        }
    }
}

fn first_diff_offset(left: &[u8], right: &[u8]) -> usize {
    let common_len = left.len().min(right.len());
    for index in 0..common_len {
        if left[index] != right[index] {
            return index;
        }
    }
    common_len
}

fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn reset_dir(path: &Path) {
    if path.exists() {
        fs::remove_dir_all(path).unwrap();
    }
    fs::create_dir_all(path).unwrap();
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .unwrap()
        .to_path_buf()
}

fn path_str(path: &Path) -> &str {
    path.to_str().unwrap()
}

struct Evidence {
    markdown: String,
}

impl Evidence {
    fn new() -> Self {
        let markdown = "# Task A11 real archive acceptance (CLI-only)\n\n- External archive tools: none.\n- GUI programs launched: none.\n- Oracle: bgs-archive structural validation + bgs-archive pack/extract self-consistency.\n\n".to_string();
        Self { markdown }
    }

    fn push_fixture(&mut self, fixture: &Fixture, result: &FixtureResult) {
        self.markdown.push_str(&format!("## {}\n\n", fixture.name));
        self.markdown
            .push_str(&format!("- Fixture: `{}`\n", fixture.path.display()));
        self.markdown.push_str(&format!(
            "- Expected auto-detect: family `{}`, version `{}`\n",
            fixture.expected_family, fixture.expected_version
        ));
        self.markdown.push_str(&format!(
            "- Auto-detect verdict: {}\n\n",
            pass_fail(result.info_ok)
        ));
        self.markdown.push_str("### `info --json`\n\n");
        self.code_block("json", &result.info_json);
        self.markdown.push_str("### `list --json`\n\n");
        self.code_block("json", &result.list_json);
        self.push_structural_table(&result.structural_rows);
        self.push_hash_table(
            &result.round_trip_rows,
            &result.missing_after_round_trip,
            &result.extra_after_round_trip,
        );
        self.markdown.push_str(&format!(
            "\n### Fixture verdict: {}\n\n",
            pass_fail(result.passed())
        ));
    }

    fn push_structural_table(&mut self, rows: &[StructuralRow]) {
        self.markdown.push_str("### Structural validation\n\n");
        self.markdown.push_str("| file | ext | expected magic | actual magic | reported size | extracted size | size match | verdict |\n");
        self.markdown
            .push_str("|---|---|---|---|---:|---:|---|---|\n");
        for row in rows {
            self.markdown.push_str(&format!(
                "| `{}` | `{}` | `{}` | `{}` | {} | {} | {} | {} |\n",
                row.path,
                row.extension,
                row.expected_magic,
                row.actual_magic,
                row.size_reported,
                row.size_extracted,
                yes_no(row.size_match),
                pass_fail(row.verdict)
            ));
        }
        self.markdown.push('\n');
    }

    fn push_hash_table(&mut self, rows: &[HashRow], missing: &[String], extra: &[String]) {
        self.markdown
            .push_str("### Self-consistency round-trip SHA256\n\n");
        self.markdown.push_str(&format!(
            "- Missing after round-trip: `{}`\n",
            missing.join(", ")
        ));
        self.markdown.push_str(&format!(
            "- Extra after round-trip: `{}`\n\n",
            extra.join(", ")
        ));
        self.markdown.push_str(
            "| file | original sha256 | round-trip sha256 | match | first diff offset |\n",
        );
        self.markdown.push_str("|---|---|---|---|---|\n");
        for row in rows {
            self.markdown.push_str(&format!(
                "| `{}` | `{}` | `{}` | {} | {} |\n",
                row.path,
                row.original_sha256,
                row.round_trip_sha256,
                yes_no(row.matches),
                row.first_diff_offset
                    .map(|offset| offset.to_string())
                    .unwrap_or_else(|| "n/a".into())
            ));
        }
        self.markdown.push('\n');
    }

    fn code_block(&mut self, language: &str, body: &str) {
        self.markdown
            .push_str(&format!("```{language}\n{}\n```\n\n", body.trim()));
    }

    fn write(&self, path: &Path) {
        fs::write(path, &self.markdown).unwrap();
    }
}

fn pass_fail(value: bool) -> &'static str {
    if value {
        "PASS"
    } else {
        "FAIL"
    }
}

fn yes_no(value: bool) -> &'static str {
    if value {
        "yes"
    } else {
        "no"
    }
}
