"""Focused in-memory and mocked-publication checks; no datasets are written."""
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import generate_robustness_data as runner
v2 = runner.v2


class GenerationTests(unittest.TestCase):
    def test_frozen_configs_and_generator_hash(self):
        config = runner.load_config()
        expected = {"R1": (101, 1101, 2101, 3101), "R2": (202, 1202, 2202, 3202),
                    "R3": (303, 1303, 2303, 3303), "R4": (404, 1404, 2404, 3404),
                    "R5": (505, 1505, 2505, 3505)}
        self.assertEqual(runner.APPROVED_RUNS, frozenset(expected))
        keys = ("baseline_seed", "planning_seed", "allocation_seed", "metadata_seed")
        self.assertEqual({r: tuple(s[k] for k in keys) for r, s in config["runs"].items()}, expected)
        self.assertEqual(runner.sha256(v2.__file__), runner.GENERATOR_SHA256)

    def test_config_tampering_rejected(self):
        with patch.object(Path, "read_bytes", return_value=b"changed"):
            with self.assertRaises(ValueError): runner.load_config()

    def test_unapproved_runs_and_missing_cli_flags_rejected_before_generation(self):
        for run in ("R0", "R6", "unknown", "../R1"):
            with self.assertRaises(PermissionError): runner.run_seeds(run)
        with patch.object(v2, "run_v2_pipeline") as generate:
            with patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
                runner.main(["--run", "R1"])
            generate.assert_not_called()

    def test_seed_reproducibility_and_planning(self):
        # Small in-memory baseline only; no full replication or publication.
        with patch.object(v2, "N_ACCOUNTS", 12):
            a = v2.generate_baseline(baseline_rng=v2.np.random.default_rng(101))
            b = v2.generate_baseline(baseline_rng=v2.np.random.default_rng(101))
            other = v2.generate_baseline(baseline_rng=v2.np.random.default_rng(102))
            v2.pd.testing.assert_frame_equal(a.accounts, b.accounts, check_exact=True)
            v2.pd.testing.assert_frame_equal(a.transactions, b.transactions, check_exact=True)
            self.assertNotEqual(v2.dataframe_fingerprint(a.transactions),
                                v2.dataframe_fingerprint(other.transactions))
            contexts = v2.build_candidate_contexts(a, months=(4,))
            plans_a = tuple(v2.plan_candidate(c, s, planning_seed=1101, metadata_seed=3101)
                            for c in contexts for s in v2.SCENARIO_NAMES)
            plans_b = tuple(v2.plan_candidate(c, s, planning_seed=1101, metadata_seed=3101)
                            for c in contexts for s in v2.SCENARIO_NAMES)
            self.assertEqual(plans_a, plans_b)
            for context in contexts:
                for plan in plans_a:
                    if plan.account_id == context.account_id: v2.validate_candidate_plan(context, plan)

    def test_existing_quota_validator_rejects_counts_and_duplicate_accounts(self):
        selected = []
        for month in (4, 5, 6):
            for scenario in v2.SCENARIO_NAMES:
                for _ in range(10):
                    selected.append(SimpleNamespace(account_id=f"ACC{len(selected)+1:05d}",
                        month=month, scenario=scenario, eligible=True, rejection_reasons=()))
        v2._validate_selected_plans(selected)
        with self.assertRaises(ValueError): v2._validate_selected_plans(selected[:-1])
        selected[-1].account_id = selected[0].account_id
        with self.assertRaises(ValueError): v2._validate_selected_plans(selected)

    def test_allocation_seed_reproducibility(self):
        candidates = [SimpleNamespace(account_id=f"ACC{i:05d}", month=month, scenario=scenario,
                                     eligible=True, rejection_reasons=())
                      for i in range(1, 161) for month in (4, 5, 6) for scenario in v2.SCENARIO_NAMES]
        def selected(seed):
            return v2.select_distinct_accounts(candidates, allocation_rng=v2.np.random.default_rng(seed))
        a, b, other = selected(2101), selected(2101), selected(2102)
        self.assertEqual(a, b)
        self.assertNotEqual([p.account_id for p in a], [p.account_id for p in other])
        v2._validate_selected_plans(a)

    def test_prior_staging_rejected_and_only_owned_staging_allowed(self):
        staging = runner.RELEASES / (".R1.staging-" + "a" * 32)
        with patch.object(v2, "_assert_no_reparse_components"), \
             patch.object(Path, "exists", autospec=True, side_effect=lambda p: p == runner.RELEASES), \
             patch.object(Path, "glob", return_value=iter([staging])):
            with self.assertRaises(FileExistsError): runner.check_destination(runner.RELEASES / "R1", "R1")
        with patch.object(v2, "_assert_no_reparse_components"), \
             patch.object(Path, "exists", autospec=True, side_effect=lambda p: p == runner.RELEASES), \
             patch.object(Path, "glob", return_value=iter([staging])):
            self.assertEqual(runner.check_destination(runner.RELEASES / "R1", "R1", owned_staging=staging),
                             runner.RELEASES / "R1")

    def test_corrupted_prepared_payload_rejected_before_any_write(self):
        prepared = SimpleNamespace(payloads={"transactions.csv": b"corrupted"})
        valid = SimpleNamespace(payloads={"transactions.csv": b"validated"})
        with patch.object(runner, "preflight"), patch.object(runner, "verify_result_identity"), \
             patch.object(v2, "_release_protected_snapshot"), \
             patch.object(v2, "prepare_v2_exports", return_value=valid), patch.object(Path, "mkdir") as mkdir:
            with self.assertRaises(ValueError): runner.publish(None, prepared, "R1", allow_sibling_staging=True)
            mkdir.assert_not_called()

    def test_outside_paths_rejected(self):
        paths = [runner.ROOT / "data/generated_v2/releases/v2_20261028", runner.ROOT / "R1",
                 runner.RELEASES / ".." / "R1", runner.RELEASES / "R1" / "nested", Path("R1")]
        for destination in paths:
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError): runner.check_destination(destination, "R1")

    def test_existing_empty_destination_rejected(self):
        with patch.object(v2, "_assert_no_reparse_components"), patch.object(Path, "exists", return_value=True):
            with self.assertRaises(FileExistsError): runner.check_destination(runner.RELEASES / "R1", "R1")

    def test_reparse_rejected(self):
        with patch.object(v2, "_assert_no_reparse_components", side_effect=ValueError("reparse")):
            with self.assertRaises(ValueError): runner.check_destination(runner.RELEASES / "R1", "R1")

    def test_unsupported_publication_stops_before_generation(self):
        with patch.object(runner, "preflight", side_effect=RuntimeError("unsupported NTFS")), \
             patch.object(v2, "run_v2_pipeline") as generate:
            with self.assertRaises(RuntimeError):
                runner.main(["--run", "R1", "--publish", "--allow-sibling-staging"])
            generate.assert_not_called()

    def test_publication_requires_authorization(self):
        with self.assertRaises(PermissionError): runner.publish(None, None, "R1")

    def test_result_seed_mismatch_rejected(self):
        metadata = {"source_sha256": runner.GENERATOR_SHA256, **runner.run_seeds("R1")}
        metadata["baseline_seed"] = 999
        result = SimpleNamespace(audits={"run_metadata": v2.pd.DataFrame(
            [{"key": k, "value": str(v)} for k, v in metadata.items()])})
        with self.assertRaises(ValueError): runner.verify_result_identity(result, "R1")

    def test_atomic_move_uses_no_replace_and_rolls_back_failure(self):
        destination = runner.RELEASES / "R1"
        staging = runner.RELEASES / (".R1.staging-" + "a" * 32)
        for success, commit_success in ((True, True), (False, False), (True, False)):
            api = {name: Mock() for name in ("create", "move", "commit", "rollback", "close")}
            api["create"].return_value = 123
            api["move"].return_value = success
            api["commit"].return_value = commit_success
            with patch.object(v2, "_windows_release_api", return_value=api), \
                 patch.object(v2, "_assert_no_reparse_components"), patch.object(Path, "exists", return_value=False):
                if success and commit_success: runner.atomic_publish(staging, destination, "R1")
                else:
                    with self.assertRaises(OSError): runner.atomic_publish(staging, destination, "R1")
            self.assertEqual(api["move"].call_args.args[-2], 0x8)
            api["close"].assert_called_once_with(123)
            if success and commit_success: api["rollback"].assert_not_called()
            else:
                api["rollback"].assert_called_once_with(123)
                if not success: api["commit"].assert_not_called()

    def test_existing_target_race_stops_atomic_move(self):
        staging = runner.RELEASES / (".R1.staging-" + "b" * 32)
        with patch.object(v2, "_assert_no_reparse_components"), \
             patch.object(Path, "exists", return_value=True), patch.object(v2, "_windows_release_api") as api:
            with self.assertRaises(FileExistsError): runner.atomic_publish(staging, runner.RELEASES / "R1", "R1")
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
