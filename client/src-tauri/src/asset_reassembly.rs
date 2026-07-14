// Build-time-sharded asset reassembly. Both NSIS (32-bit mmap) and MSI (2GB
// CAB limit) reject single files over ~2GB; scripts/split_asset.ps1 splits
// the bundled model + grype-db into <2GB `.partNNN` shards + a manifest.json
// at build time. This module streams them back together on first launch,
// verifying a sha256 of the whole file. See
// docs/superpowers/specs/2026-07-14-first-run-asset-reassembly-design.md.

use std::fs::{self, File};
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};

use serde::Deserialize;
use sha2::{Digest, Sha256};

#[derive(Debug)]
pub enum ReassemblyError {
    Io(io::Error),
    ManifestMissing,
    ManifestCorrupt(String),
    ChecksumMismatch { expected: String, actual: String },
}

impl From<io::Error> for ReassemblyError {
    fn from(e: io::Error) -> Self {
        ReassemblyError::Io(e)
    }
}

impl std::fmt::Display for ReassemblyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReassemblyError::Io(e) => write!(f, "I/O error: {e}"),
            ReassemblyError::ManifestMissing => write!(f, "manifest.json is missing"),
            ReassemblyError::ManifestCorrupt(msg) => write!(f, "manifest.json is corrupt: {msg}"),
            ReassemblyError::ChecksumMismatch { expected, actual } => {
                write!(f, "checksum mismatch: expected {expected}, got {actual}")
            }
        }
    }
}

#[derive(Debug, Deserialize)]
struct Manifest {
    file: String,
    total_size: u64,
    sha256: String,
    part_count: u32,
}

pub struct AssetSpec {
    pub file_name: &'static str,
}

pub const MODEL_ASSET: AssetSpec = AssetSpec { file_name: "astra.gguf" };
pub const GRYPE_DB_ASSET: AssetSpec = AssetSpec { file_name: "vulnerability.db" };

fn manifest_path(resource_dir: &Path, spec: &AssetSpec) -> PathBuf {
    resource_dir.join(format!("{}.manifest.json", spec.file_name))
}

fn part_path(resource_dir: &Path, spec: &AssetSpec, index: u32) -> PathBuf {
    resource_dir.join(format!("{}.part{:03}", spec.file_name, index))
}

fn done_marker_path(target_dir: &Path, spec: &AssetSpec) -> PathBuf {
    target_dir.join(format!("{}.done", spec.file_name))
}

fn load_manifest(resource_dir: &Path, spec: &AssetSpec) -> Result<Manifest, ReassemblyError> {
    let path = manifest_path(resource_dir, spec);
    if !path.exists() {
        return Err(ReassemblyError::ManifestMissing);
    }
    let text = fs::read_to_string(&path)?;
    let manifest: Manifest =
        serde_json::from_str(&text).map_err(|e| ReassemblyError::ManifestCorrupt(e.to_string()))?;
    if manifest.file != spec.file_name {
        return Err(ReassemblyError::ManifestCorrupt(format!(
            "manifest is for '{}', expected '{}'",
            manifest.file, spec.file_name
        )));
    }
    Ok(manifest)
}

/// Copies every file in `resource_dir` that is neither a `.partNNN` shard nor
/// the asset's own manifest into `target_dir` — the grype-db resource
/// directory also holds small companion metadata files (e.g. `metadata.json`,
/// `listing.json` from `grype db update`) that must sit alongside the
/// reassembled `vulnerability.db` for `GRYPE_DB_CACHE_DIR` to be a valid
/// cache directory.
fn copy_companion_files(
    resource_dir: &Path,
    spec: &AssetSpec,
    target_dir: &Path,
) -> Result<(), ReassemblyError> {
    let manifest_name = format!("{}.manifest.json", spec.file_name);
    let part_prefix = format!("{}.part", spec.file_name);
    for entry in fs::read_dir(resource_dir)? {
        let entry = entry?;
        let file_name = entry.file_name();
        let name = file_name.to_string_lossy();
        if name == manifest_name.as_str() || name.starts_with(&part_prefix) || name == spec.file_name {
            continue;
        }
        if entry.file_type()?.is_file() {
            fs::copy(entry.path(), target_dir.join(&*name))?;
        }
    }
    Ok(())
}

/// Ensures `spec`'s asset is fully reassembled and checksum-verified at
/// `target_dir/<file_name>`, reading its `.partNNN` shards + manifest from
/// `resource_dir`. Idempotent: returns immediately on subsequent calls once a
/// `.done` marker with a matching hash and a size-matching target file
/// exist — this avoids re-hashing a multi-gigabyte file on every launch.
/// Calls `progress(bytes_written, total_size)` periodically while streaming.
pub fn ensure_ready(
    resource_dir: &Path,
    target_dir: &Path,
    spec: &AssetSpec,
    mut progress: impl FnMut(u64, u64),
) -> Result<PathBuf, ReassemblyError> {
    fs::create_dir_all(target_dir)?;
    let target_path = target_dir.join(spec.file_name);
    let manifest = load_manifest(resource_dir, spec)?;
    let done_path = done_marker_path(target_dir, spec);

    if done_path.exists() {
        if let Ok(recorded_hash) = fs::read_to_string(&done_path) {
            if recorded_hash.trim() == manifest.sha256 {
                if let Ok(meta) = fs::metadata(&target_path) {
                    if meta.len() == manifest.total_size {
                        return Ok(target_path);
                    }
                }
            }
        }
    }

    let tmp_path = target_dir.join(format!("{}.tmp", spec.file_name));
    let _ = fs::remove_file(&tmp_path);

    {
        let mut writer = BufWriter::new(File::create(&tmp_path)?);
        let mut hasher = Sha256::new();
        let mut written: u64 = 0;
        let mut buf = [0u8; 1024 * 1024];

        for index in 0..manifest.part_count {
            let part = part_path(resource_dir, spec, index);
            let mut reader = BufReader::new(File::open(&part)?);
            loop {
                let n = reader.read(&mut buf)?;
                if n == 0 {
                    break;
                }
                writer.write_all(&buf[..n])?;
                hasher.update(&buf[..n]);
                written += n as u64;
                progress(written, manifest.total_size);
            }
        }
        writer.flush()?;

        let actual = format!("{:x}", hasher.finalize());
        if actual != manifest.sha256 {
            drop(writer);
            let _ = fs::remove_file(&tmp_path);
            return Err(ReassemblyError::ChecksumMismatch {
                expected: manifest.sha256,
                actual,
            });
        }
    }

    fs::rename(&tmp_path, &target_path)?;
    fs::write(&done_path, &manifest.sha256)?;
    copy_companion_files(resource_dir, spec, target_dir)?;

    Ok(target_path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    const TEST_ASSET: AssetSpec = AssetSpec { file_name: "test.bin" };

    /// Writes `parts` as `test.bin.part000.. ` plus a matching manifest.json
    /// into `resource_dir`. Returns the concatenated bytes for assertions.
    fn write_fixture(resource_dir: &Path, parts: &[&[u8]]) -> Vec<u8> {
        let mut whole = Vec::new();
        for (i, part) in parts.iter().enumerate() {
            whole.extend_from_slice(part);
            fs::write(part_path(resource_dir, &TEST_ASSET, i as u32), part).unwrap();
        }
        let sha256 = format!("{:x}", Sha256::digest(&whole));
        let manifest = format!(
            r#"{{"file":"test.bin","total_size":{},"sha256":"{}","part_count":{}}}"#,
            whole.len(),
            sha256,
            parts.len(),
        );
        fs::write(manifest_path(resource_dir, &TEST_ASSET), manifest).unwrap();
        whole
    }

    #[test]
    fn reassembles_parts_into_the_expected_whole_file() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        let whole = write_fixture(resource_dir.path(), &[b"hello ", b"world", b"!"]);

        let mut calls = Vec::new();
        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |w, t| {
            calls.push((w, t));
        })
        .unwrap();

        assert_eq!(fs::read(&result).unwrap(), whole);
        assert!(!calls.is_empty(), "progress callback should fire at least once");
    }

    #[test]
    fn second_call_is_idempotent_and_skips_reading_parts() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        write_fixture(resource_dir.path(), &[b"abc", b"def"]);

        ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {}).unwrap();

        // If the second call actually re-read the parts, deleting one here
        // would make it fail with an I/O error. It must not, because the
        // `.done` marker short-circuits it.
        fs::remove_file(part_path(resource_dir.path(), &TEST_ASSET, 0)).unwrap();

        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(result.is_ok());
    }

    #[test]
    fn corrupted_part_produces_checksum_mismatch_then_recovers_on_retry() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        write_fixture(resource_dir.path(), &[b"correct-bytes-1", b"correct-bytes-2"]);

        fs::write(part_path(resource_dir.path(), &TEST_ASSET, 0), b"corrupted!!!!!!").unwrap();

        let first = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(matches!(first, Err(ReassemblyError::ChecksumMismatch { .. })));

        // Fix the part back to what the manifest expects and retry — this is
        // what main.rs's auto-retry-once policy does at the orchestration level.
        fs::write(part_path(resource_dir.path(), &TEST_ASSET, 0), b"correct-bytes-1").unwrap();
        let second = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(second.is_ok());
    }

    #[test]
    fn truncated_last_part_is_detected_as_a_checksum_mismatch() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        write_fixture(resource_dir.path(), &[b"full-part-one", b"full-part-two"]);

        fs::write(part_path(resource_dir.path(), &TEST_ASSET, 1), b"trunc").unwrap();

        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(matches!(result, Err(ReassemblyError::ChecksumMismatch { .. })));
    }

    #[test]
    fn missing_manifest_is_reported_distinctly() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        // No fixture written — manifest.json is absent.

        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(matches!(result, Err(ReassemblyError::ManifestMissing)));
    }
}
