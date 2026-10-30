#!/usr/bin/env python3
"""UNREADY: source-only proposal for one exact, owned CI credential cleanup.

Root and actual Claude review are required before changing REVIEW_STATE.
Original metadata is fetched once by the ordinary CI job token and stays in RAM.
This file must be copied to tools/cleanup_ci11933_in_memory.py on the isolated
diagnostic branch. No credential include, archive, PEM, or mode.txt is read.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
import urllib.error
import urllib.request

REVIEW_STATE = "ROOT_AND_ACTUAL_CLAUDE_APPROVED"
REQUIRED_REVIEW_STATE = "ROOT_AND_ACTUAL_CLAUDE_APPROVED"
FLAG = "ci11933-owned-cloud-cleanup-reviewed-v1"
SOURCE_SHA = "35589b1ed7887aca544ac1c09e67a85c3ea21660"
HELPER_SHA256 = "736e9f3d5489d4cf43382b3666c4b5d784ab299ef03977e9af702871c55cbbcb"
CREATOR_SHA256 = "1d3875d9486f9520262c2c242e651a75066d2222346e1bca478578d6bdd713cb"
TERMINAL_SHA256 = "84eb032ce6cc84e9daf0329851519c1aa44b48b4c31fd503769b0449d0db0f62"
PROJECT_ID, ORIGINAL_PIPELINE_ID, PREPARATION_JOB_ID = "38", "11933", "73354"
BRANCH = "codex/184-ci11933-credential-finalize-only"
API_BASE = "https://gitlab.saffti.jp/api/v4"
META_ROUTE = "/projects/38/jobs/73354/artifacts/artifacts/prepare_rx65n_bg96_mqtt_credentials/iot_credentials_meta.json"
PROJECTION_PATH = Path("sanitized_cleanup_projection.json")
INTENT_PATH = Path("ci11933_cleanup_intent_once.json")


class Hold(Exception):
    """Closed local reason; never carries server bodies, identities, or tokens."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Hold("metadata_fetch_failed")


class MemoryMeta:
    def __init__(self, text):
        self.text = text

    def is_file(self):
        return True

    def read_text(self, encoding="utf-8"):
        return self.text


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Hold("metadata_validation_failed")
        result[key] = value
    return result


def main():
    if PROJECTION_PATH.exists():
        print("Existing projection; repeat execution refused.")
        return 1
    projection = {
        "schema_version": 1,
        "original_preparation_source_commit": SOURCE_SHA,
        "canonical_cleanup_sha256": HELPER_SHA256,
        "canonical_creator_sha256": CREATOR_SHA256,
        "original_terminal_sha256": TERMINAL_SHA256,
        "original_project_id": 38,
        "original_pipeline_id": 11933,
        "original_preparation_job_id": 73354,
        "cleanup_pipeline_id": 0,
        "cleanup_job_id": 0,
        "cleanup_source_commit": "",
        "review_ready": False,
        "oneuse_intent_written": False,
        "canonical_creator_verified": False,
        "hold_reason": "not_started",
        "ci_context_verified": False,
        "canonical_helper_verified": False,
        "metadata_http_attempt_count": 0,
        "metadata_http_403": False,
        "metadata_http_404": False,
        "metadata_loaded": False,
        "metadata_identity_verified": False,
        "aws_account_verified": False,
        "ownership_preflight_passed": False,
        "foreign_relationship_detected": False,
        "aws_call_count": 0,
        "mutation_attempt_count": 0,
        "canonical_action_count": 0,
        "canonical_error_count": 0,
        "verified_absent_resource_count": 0,
        "cleanup_verified": False,
        "hold": True,
    }
    summary = {}
    canonical_output = io.StringIO()
    try:
        if REVIEW_STATE != REQUIRED_REVIEW_STATE:
            raise Hold("unready")
        projection["review_ready"] = True
        env = os.environ
        if not (
            env.get("CI") == "true"
            and env.get("CI_PROJECT_ID") == PROJECT_ID
            and env.get("GITLAB_USER_ID") == "38"
            and env.get("CI_PIPELINE_SOURCE") == "api"
            and env.get("CI_COMMIT_BRANCH") == BRANCH
            and env.get("CI_API_V4_URL") == API_BASE
            and env.get("RUN_CI11933_CLOUD_CLEANUP_RECOVERY") == FLAG
            and env.get("CI_JOB_TOKEN")
        ):
            raise Hold("ci_context_failed")
        pipeline_id, job_id = env.get("CI_PIPELINE_ID", ""), env.get("CI_JOB_ID", "")
        commit = env.get("CI_COMMIT_SHA", "")
        if not (pipeline_id.isdecimal() and job_id.isdecimal() and re.fullmatch(r"[0-9a-f]{40}", commit)):
            raise Hold("ci_context_failed")
        if pipeline_id == ORIGINAL_PIPELINE_ID or job_id in {"73354", "73357"}:
            raise Hold("ci_context_failed")
        projection.update(cleanup_pipeline_id=int(pipeline_id), cleanup_job_id=int(job_id), cleanup_source_commit=commit)
        projection["ci_context_verified"] = True
        region = env.get("AWS_DEFAULT_REGION", "")
        prefix = env.get("RX65N_BG96_THING_NAME_PREFIX", "")
        policy = env.get("RX65N_BG96_IOT_POLICY_NAME", "")
        if not (region and prefix and policy):
            raise Hold("ci_context_failed")
        expected_thing = prefix + "-" + ORIGINAL_PIPELINE_ID

        helper_path = Path(env["CI_PROJECT_DIR"]) / "tools" / "cleanup_bg96_iot_credentials.py"
        # Git for Windows may check out CRLF. Pin canonical UTF-8 source with LF.
        helper_source = helper_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if hashlib.sha256(helper_source.encode("utf-8")).hexdigest() != HELPER_SHA256:
            raise Hold("helper_pin_failed")
        canonical = types.ModuleType("owned_ci11933_canonical_cleanup")
        canonical.__file__ = str(helper_path)
        exec(compile(helper_source, str(helper_path), "exec"), canonical.__dict__)
        projection["canonical_helper_verified"] = True
        creator_source = (Path(env["CI_PROJECT_DIR"]) / "tools" / "create_bg96_iot_credentials.py").read_text(encoding="utf-8").replace("\r\n", "\n")
        if hashlib.sha256(creator_source.encode("utf-8")).hexdigest() != CREATOR_SHA256:
            raise Hold("creator_pin_failed")
        projection["canonical_creator_verified"] = True
        with INTENT_PATH.open("x", encoding="utf-8") as intent:
            json.dump({"original_preparation_source_commit": SOURCE_SHA, "original_pipeline_id": 11933,
                "original_prepare_job_id": 73354, "cleanup_pipeline_id": int(pipeline_id),
                "cleanup_job_id": int(job_id), "cleanup_source_commit": commit,
                "actor_id": 38, "metadata_GET_max": 1, "mutation_max": 5,
                "helper_sha256": HELPER_SHA256, "creator_sha256": CREATOR_SHA256,
                "no_replay": True}, intent)
        projection["oneuse_intent_written"] = True


        # Exactly one raw-single-file request. No redirect, retry, fallback, or archive.
        request = urllib.request.Request(API_BASE + META_ROUTE, headers={"JOB-TOKEN": env["CI_JOB_TOKEN"], "Accept-Encoding": "identity"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        projection["metadata_http_attempt_count"] = 1
        try:
            with opener.open(request, timeout=30) as response:
                if response.status != 200 or response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise Hold("metadata_fetch_failed")
                body = response.read(65537)
        except urllib.error.HTTPError as error:
            projection["metadata_http_403"] = error.code == 403
            projection["metadata_http_404"] = error.code == 404
            error.close()
            raise Hold("metadata_fetch_failed") from None
        if len(body) > 65536:
            raise Hold("metadata_validation_failed")
        meta_text = body.decode("utf-8-sig")
        del body
        meta = json.loads(meta_text, object_pairs_hook=unique_object)
        if not isinstance(meta, dict):
            raise Hold("metadata_validation_failed")
        projection["metadata_loaded"] = True
        if not all(isinstance(meta.get(key), str) and meta[key] for key in (
            "thing_name", "policy_name", "region", "certificate_id", "certificate_arn"
        )):
            raise Hold("metadata_validation_failed")
        cert_id, cert_arn = meta["certificate_id"], meta["certificate_arn"]
        arn_match = re.fullmatch(r"arn:aws:iot:" + re.escape(region) + r":([0-9]{12}):cert/([0-9a-f]{64})", cert_arn)
        if not (
            meta["thing_name"] == expected_thing
            and meta["policy_name"] == policy
            and meta["region"] == region
            and re.fullmatch(r"[0-9a-f]{64}", cert_id)
            and arn_match and arn_match.group(2) == cert_id
        ):
            raise Hold("metadata_validation_failed")
        projection["metadata_identity_verified"] = True

        # Keep the existing normal Windows AWS CI identity; never select another
        # profile, credential source, OS account, WSL identity, or local secret file.
        if env.get("AWS_CLI_USE_PYTHON_MODULE") == "1":
            aws_prefix = [sys.executable, "-m", "awscli"]
        else:
            executable = shutil.which("aws")
            if not executable or Path(executable).suffix.lower() != ".exe":
                raise Hold("aws_unavailable")
            aws_prefix = [executable]
        aws_env = dict(env, AWS_MAX_ATTEMPTS="1", AWS_RETRY_MODE="standard", AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off")
        thing_args = ["iot", "list-thing-principals", "--thing-name", expected_thing]
        reverse_args = ["iot", "list-principal-things", "--principal", cert_arn]
        attached_args = ["iot", "list-attached-policies", "--target", cert_arn]
        policy_args = ["iot", "list-principal-policies", "--principal", cert_arn]
        mutations = {
            ("iot", "detach-thing-principal", "--thing-name", expected_thing, "--principal", cert_arn),
            ("iot", "detach-policy", "--policy-name", policy, "--target", cert_arn),
            ("iot", "update-certificate", "--certificate-id", cert_id, "--new-status", "INACTIVE"),
            ("iot", "delete-certificate", "--certificate-id", cert_id),
            ("iot", "delete-thing", "--thing-name", expected_thing),
        }
        describe_cert = ("iot", "describe-certificate", "--certificate-id", cert_id)
        describe_thing = ("iot", "describe-thing", "--thing-name", expected_thing)
        allowed = {tuple(thing_args), tuple(reverse_args), tuple(attached_args), tuple(policy_args),
                   ("sts", "get-caller-identity"), describe_cert, describe_thing} | mutations

        def run_aws(args, call_region):
            key = tuple(args)
            if key not in allowed or call_region != region:
                raise Hold("operation_not_allowed")
            if key in mutations:
                if not projection["ownership_preflight_passed"]:
                    raise Hold("ownership_not_verified")
                projection["mutation_attempt_count"] += 1
            command = aws_prefix + list(args) + ["--region", region, "--output", "json", "--no-paginate"]
            # Canonical verification needs only return codes; never request PEM output.
            if key == describe_cert:
                command += ["--query", "certificateDescription.{id:certificateId,status:status}"]
            elif key == describe_thing:
                command += ["--query", "{name:thingName}"]
            projection["aws_call_count"] += 1
            result = subprocess.run(command, capture_output=True, text=True, shell=False, env=aws_env, timeout=90)
            error_code = canonical.aws_error_code(result.stderr)
            payload, parse_error = {}, None
            if result.returncode == 0 and result.stdout.strip():
                try:
                    payload = json.loads(result.stdout)
                except json.JSONDecodeError:
                    parse_error = "invalid_json"
            if error_code in {"AccessDenied", "AccessDeniedException", "UnauthorizedException", "ForbiddenException"}:
                raise Hold("aws_access_denied")
            if isinstance(payload, dict) and any(payload.get(k) for k in ("nextToken", "nextMarker", "NextToken", "NextMarker")):
                raise Hold("pagination_not_complete")
            return {"returncode": result.returncode, "payload": payload,
                    "aws_error_code": error_code, "parse_error": parse_error}

        def discovery(args, key, policies=False):
            result = run_aws(args, region)
            if not canonical.succeeded_or_absent(result):
                raise Hold("ownership_discovery_failed")
            if result["aws_error_code"] == canonical.NOT_FOUND_ERROR:
                return set()
            payload = result["payload"]
            if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
                raise Hold("ownership_discovery_failed")
            values = payload[key]
            if policies:
                if not all(isinstance(value, dict) and isinstance(value.get("policyName"), str) and value["policyName"] for value in values):
                    raise Hold("ownership_discovery_failed")
                values = [value["policyName"] for value in values]
            if not all(isinstance(value, str) and value for value in values):
                raise Hold("ownership_discovery_failed")
            return set(values)

        identity = run_aws(["sts", "get-caller-identity"], region)
        if not (identity["returncode"] == 0 and identity["parse_error"] is None
                and isinstance(identity["payload"], dict)
                and identity["payload"].get("Account") == arn_match.group(1)):
            raise Hold("aws_account_mismatch")
        projection["aws_account_verified"] = True
        principals = discovery(thing_args, "principals")
        things = discovery(reverse_args, "things")
        policies = discovery(attached_args, "policies", policies=True)
        if principals - {cert_arn} or things - {expected_thing} or policies - {policy}:
            projection["foreign_relationship_detected"] = True
            raise Hold("foreign_relationship")
        projection["ownership_preflight_passed"] = True

        def keep_summary_in_memory(_path, payload):
            summary.clear()
            summary.update(payload)

        canonical.parse_args = lambda: argparse.Namespace(
            meta_json=MemoryMeta(meta_text), region=region,
            expected_thing_name=expected_thing, expected_policy_name=policy,
            output_json="RAM_ONLY",
        )
        canonical.write_json = keep_summary_in_memory
        canonical.run_aws = run_aws
        # The unchanged canonical helper prints raw identities. Capture and discard.
        with contextlib.redirect_stdout(canonical_output), contextlib.redirect_stderr(canonical_output):
            status = canonical.main()
        projection["cleanup_verified"] = bool(status == 0 and summary.get("verification", {}).get("passed"))
        projection["hold"] = not projection["cleanup_verified"]
        projection["hold_reason"] = "none" if projection["cleanup_verified"] else "canonical_verification_failed"
    except Hold as error:
        projection["hold"] = True
        allowed_reasons = {"unready", "ci_context_failed", "helper_pin_failed", "creator_pin_failed",
            "metadata_fetch_failed", "metadata_validation_failed", "aws_unavailable",
            "operation_not_allowed", "ownership_not_verified", "aws_access_denied",
            "pagination_not_complete", "ownership_discovery_failed", "aws_account_mismatch", "foreign_relationship"}
        projection["hold_reason"] = str(error) if str(error) in allowed_reasons else "internal_hold"
    except Exception as error:
        projection["hold"] = True
        projection["hold_reason"] = "internal_exception"
        projection["exception_class"] = type(error).__name__
    finally:
        projection["canonical_action_count"] = len(summary.get("actions", []))
        projection["canonical_error_count"] = len(summary.get("errors", []))
        projection["verified_absent_resource_count"] = sum(
            item.get("state") == "absent" for item in summary.get("verification", {}).get("resources", [])
        )
        canonical_output.close()
        with PROJECTION_PATH.open("x", encoding="utf-8") as output:
            output.write(json.dumps(projection, indent=2) + "\n")
    print("Sanitized owned-cleanup projection written.")
    return 0 if projection["cleanup_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
