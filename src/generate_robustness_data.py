"""Generation-only R1-R5 releases; reuse the verified V2 pipeline without modifying it."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

import generate_data_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "v2_robustness_seeds.json"
RELEASES = ROOT / "data" / "robustness" / "releases"
GENERATOR_SHA256 = "21f0e10549227079c2dd2e76315e9498afca63cdaabea24323751feaedfd5880"
CONFIG_SHA256 = "a8d0c42d005a6d5d1f8df347f9bbc513c8f118b0c6874a9537125f2d70d99667"
APPROVED_RUNS = frozenset({"R1", "R2", "R3", "R4", "R5"})  # Explicitly approved frozen runs.


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_config():
    if sha256(Path(v2.__file__)) != GENERATOR_SHA256:
        raise ValueError("Verified V2 generator hash mismatch; refusing generation.")
    payload = CONFIG.read_bytes()
    if hashlib.sha256(payload).hexdigest() != CONFIG_SHA256:
        raise ValueError("Frozen seed configuration changed; no substitution permitted.")
    config = json.loads(payload)
    if config["generator_sha256"] != GENERATOR_SHA256:
        raise ValueError("Configuration generator identity mismatch.")
    return config


def run_seeds(run):
    config = load_config()
    if run not in APPROVED_RUNS:
        raise PermissionError("Run is outside the explicitly approved frozen R1-R5 configurations.")
    return dict(config["runs"][run])


def check_destination(destination, run, *, owned_staging=None):
    """Allow one exact child of the fixed release root; reject links and reuse."""
    run_seeds(run)
    destination = Path(destination)
    expected = RELEASES / run
    if not destination.is_absolute() or destination != expected or ".." in destination.parts:
        raise ValueError("Publication must use the configured child of data/robustness/releases/.")
    v2._assert_no_reparse_components(destination)
    if ROOT.resolve() != ROOT or Path(v2.ROOT_DIR) != ROOT:
        raise ValueError("Unexpected workspace root.")
    if destination.resolve() != expected or RELEASES.resolve() != RELEASES:
        raise ValueError("Unexpected resolved publication directory.")
    if destination.exists():
        raise FileExistsError(f"Destination already exists; no replacement permitted: {destination}")
    # A failed attempt is retained for inspection, never retried automatically.
    prior_staging = set(RELEASES.glob(f".{run}.staging-*")) if RELEASES.exists() else set()
    allowed_staging = set() if owned_staging is None else {Path(owned_staging)}
    if prior_staging != allowed_staging:
        raise FileExistsError("Unexpected or prior staging; stop for review before any further attempt.")
    return destination


def preflight(destination, run, *, owned_staging=None):
    destination = check_destination(destination, run, owned_staging=owned_staging)
    api = v2._windows_release_api()  # Same platform requirements; no fallback.
    name, filesystem = ctypes.create_unicode_buffer(261), ctypes.create_unicode_buffer(261)
    serial, maximum, flags = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    anchor = destination.anchor
    if not api["volume"](anchor, name, len(name), ctypes.byref(serial), ctypes.byref(maximum),
                         ctypes.byref(flags), filesystem, len(filesystem)):
        raise ctypes.WinError(ctypes.get_last_error())
    if api["drive_type"](anchor) != 3 or filesystem.value != "NTFS" or not flags.value & 0x00200000:
        raise RuntimeError("Local fixed NTFS transaction support is required; no fallback.")
    return destination


def atomic_publish(staging, destination, run):
    """Destination-aware equivalent of V2's TxF move, with the same no-replace flags."""
    run_seeds(run)
    staging, destination = Path(staging), Path(destination)
    prefix = f".{run}.staging-"
    suffix = staging.name.removeprefix(prefix)
    if (destination != RELEASES / run or staging.parent != RELEASES
            or staging.anchor != destination.anchor or not staging.name.startswith(prefix)
            or len(suffix) != 32 or any(c not in "0123456789abcdef" for c in suffix)):
        raise ValueError("Invalid destination or owned sibling staging namespace.")
    v2._assert_no_reparse_components(staging)
    v2._assert_no_reparse_components(destination)
    if destination.exists():
        raise FileExistsError("Release target appeared; refusing replacement.")
    api = v2._windows_release_api()
    transaction = api["create"](None, None, 0, 0, 0, 120000, f"Validated robustness {run} publication")
    if transaction in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    committed = False
    try:
        # WRITE_THROUGH only, exactly as in V2. No REPLACE_EXISTING or COPY_ALLOWED.
        if not api["move"](str(staging), str(destination), None, None, 0x8, transaction):
            raise ctypes.WinError(ctypes.get_last_error())
        if not api["commit"](transaction):
            raise ctypes.WinError(ctypes.get_last_error())
        committed = True
    finally:
        if not committed:
            api["rollback"](transaction)
        api["close"](transaction)


def verify_result_identity(result, run):
    seeds = run_seeds(run)
    metadata = result.audits["run_metadata"].set_index("key")["value"]
    if metadata["source_sha256"] != GENERATOR_SHA256:
        raise ValueError("Result generator identity mismatch.")
    if any(int(metadata[key]) != value for key, value in seeds.items()):
        raise ValueError("Result seeds disagree with the frozen configuration.")


def publish(result, prepared, run, *, allow_sibling_staging=False):
    if allow_sibling_staging is not True:
        raise PermissionError("Explicit sibling staging authorization is required.")
    destination = preflight(RELEASES / run, run)
    snapshot = v2._release_protected_snapshot()
    verify_result_identity(result, run)
    # Reuse all integrated and serialization validation, before creating anything.
    validated = v2.prepare_v2_exports(result)
    if validated.payloads != prepared.payloads:
        raise ValueError("Prepared CSV bytes disagree with fresh validated serialization.")
    v2.pd.testing.assert_frame_equal(validated.schema, prepared.schema, check_exact=True)
    v2.pd.testing.assert_frame_equal(validated.manifest, prepared.manifest, check_exact=True)
    v2.pd.testing.assert_frame_equal(validated.inventory, prepared.inventory, check_exact=True)
    v2._verify_release_protection(snapshot)
    preflight(destination, run)
    # Only the new robustness hierarchy may be created; no original path is moved.
    destination.parent.mkdir(parents=True, exist_ok=True)
    v2._assert_no_reparse_components(destination.parent)
    staging = destination.parent / f".{run}.staging-{uuid.uuid4().hex}"
    staging.mkdir(exist_ok=False)
    committed = False
    try:
        for filename in v2.EXPECTED_RELEASE_FILENAMES:
            with (staging / filename).open("xb") as handle:
                payload = prepared.payloads[filename]
                if handle.write(payload) != len(payload):
                    raise OSError(f"Short staged write: {filename}")
                handle.flush()
                os.fsync(handle.fileno())
        staged_hashes = v2.validate_release_directory(staging, result, prepared)
        v2._verify_release_protection(snapshot, staging)
        # Repeat every path, platform and config check, allowing only our staging.
        preflight(destination, run, owned_staging=staging)
        atomic_publish(staging, destination, run)
        committed = True
        final_hashes = v2.validate_release_directory(destination, result, prepared)
        if final_hashes != staged_hashes:
            raise ValueError("Published hashes differ from validated staged bytes.")
        v2._verify_release_protection(snapshot, destination)
        verify_result_identity(result, run)
        return build_report(result, run, destination, final_hashes)
    except Exception as error:
        location = destination if committed else staging
        raise RuntimeError(
            f"Publication stopped; committed={committed}; inspection_path={location}; "
            "no overwrite, deletion, retry, or nontransactional fallback performed."
        ) from error


def build_report(result, run, destination, hashes):
    positives = result.labels.loc[result.labels["is_injected_anomaly"].eq(1)]
    allocations = positives.groupby(["month", "scenario"], sort=True).size()
    return {
        "status": "published_and_verified", "run": run,
        "generator_sha256": GENERATOR_SHA256, "config_sha256": CONFIG_SHA256,
        "runner_sha256": sha256(__file__), "seeds": run_seeds(run),
        "output_directory": str(destination),
        "publication_method": "NTFS_transactional_directory_move_no_replace",
        "counts": {"accounts": len(result.accounts),
                   "baseline_transactions": len(result.baseline.transactions),
                   "transactions": len(result.transactions), "account_months": len(result.features),
                   "injected_account_months": len(positives),
                   "distinct_injected_accounts": positives["account_id"].nunique(),
                   "training_anomalies": int(positives["month"].isin([1, 2, 3]).sum()),
                   "validation_anomalies": int(positives["month"].eq(4).sum()),
                   "test_anomalies": int(positives["month"].isin([5, 6]).sum())},
        "scenario_allocations": [{"month": int(month), "scenario": scenario, "count": int(count)}
                                 for (month, scenario), count in allocations.items()],
        "integrity_checks": result.audits["integrity_checks"].to_dict("records"),
        "files_sha256": hashes, "file_count": len(hashes),
        "protected_files_unchanged": True, "staging_retained": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", choices=sorted(APPROVED_RUNS), required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--allow-sibling-staging", action="store_true")
    args = parser.parse_args(argv)
    if not args.publish or not args.allow_sibling_staging:
        parser.error("Generation requires --publish and --allow-sibling-staging; no implicit runs.")
    seeds = run_seeds(args.run)
    preflight(RELEASES / args.run, args.run)
    print(f"Generating {args.run} in memory with frozen seeds {seeds}", file=sys.stderr, flush=True)
    result = v2.run_v2_pipeline(**seeds)
    print("Pipeline validated; preparing the existing 21-file export.", file=sys.stderr, flush=True)
    prepared = v2.prepare_v2_exports(result)
    print("Export validated; publishing with no replacement.", file=sys.stderr, flush=True)
    report = publish(result, prepared, args.run, allow_sibling_staging=True)
    print(json.dumps(report, indent=2, sort_keys=True, default=int))
    return report


if __name__ == "__main__":
    main()
