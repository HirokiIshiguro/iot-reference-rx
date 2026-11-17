"""AWS resources of tools/ci/rxci.py.

Every resource a test creates carries its owner in the name: rxci-p<pipeline>-j<job>-<label>.
Cleanup needs nothing but that name, so it also works after a cancelled pipeline:
a later pipeline removes what is older than a few hours.
"""
from __future__ import annotations

import os
import time

PREFIX = "rxci-p"


def owner() -> str:
    return f"{PREFIX}{os.environ.get('CI_PIPELINE_ID', '0')}-j{os.environ.get('CI_JOB_ID', '0')}"


def create_thing(session, name: str, policy: str) -> dict:
    """Create a thing with an active certificate that has the given IoT policy."""
    iot = session.client("iot")
    iot.create_thing(thingName=name, attributePayload={"attributes": {"created": str(int(time.time()))}})
    keys = iot.create_keys_and_certificate(setAsActive=True)
    iot.attach_policy(policyName=policy, target=keys["certificateArn"])
    iot.attach_thing_principal(thingName=name, principal=keys["certificateArn"])
    print(f"aws: created thing {name}", flush=True)
    return {"thing": name, "certificate": keys["certificatePem"], "private_key": keys["keyPair"]["PrivateKey"]}


def delete_thing(iot, name: str) -> None:
    """Delete a thing, its certificates and their attachments. Missing parts are not an error."""
    missing = iot.exceptions.ResourceNotFoundException
    try:
        principals = iot.list_thing_principals(thingName=name)["principals"]
    except missing:
        return
    for principal in principals:
        iot.detach_thing_principal(thingName=name, principal=principal)
        if ":cert/" not in principal:
            continue
        certificate = principal.split("/")[-1]
        for policy in iot.list_attached_policies(target=principal)["policies"]:
            iot.detach_policy(policyName=policy["policyName"], target=principal)
        try:
            iot.update_certificate(certificateId=certificate, newStatus="INACTIVE")
            iot.delete_certificate(certificateId=certificate, forceDelete=True)
        except missing:
            pass
    for attempt in range(10):
        try:
            iot.delete_thing(thingName=name)
            break
        except missing:
            break
        except iot.exceptions.InvalidRequestException:
            time.sleep(2)       # the detachment above is not visible yet
    else:
        raise RuntimeError(f"Thing {name} still has principals attached.")
    print(f"aws: deleted thing {name}", flush=True)


def owned_things(iot, prefix: str) -> list[dict]:
    things = []
    for page in iot.get_paginator("list_things").paginate():
        things.extend(thing for thing in page["things"] if thing["thingName"].startswith(prefix))
    return things


def sweep(session, *, prefix: str = "", stale_hours: float = 0) -> list[str]:
    """Delete things whose name starts with prefix, and things of any pipeline older than stale_hours."""
    iot = session.client("iot")
    deleted = []
    now = time.time()
    for thing in owned_things(iot, PREFIX):
        name = thing["thingName"]
        created = float(thing.get("attributes", {}).get("created", "0") or 0)
        mine = bool(prefix) and name.startswith(prefix)
        stale = stale_hours > 0 and created > 0 and now - created > stale_hours * 3600
        if mine or stale:
            delete_thing(iot, name)
            deleted.append(name)
    return deleted


def delete_fleet_resources(session, summary_path) -> list[str]:
    """Delete the thing and certificate a board created through Fleet Provisioning.

    Their names are chosen by the provisioning template, so the test tool records them in
    its summary file as soon as the board reports them.
    """
    import json
    from pathlib import Path

    path = Path(summary_path)
    if not path.is_file():
        return []
    summary = json.loads(path.read_text(encoding="utf-8"))
    iot = session.client("iot")
    deleted = []
    thing = summary.get("thing_name")
    certificate = summary.get("certificate_id")
    if thing:
        delete_thing(iot, thing)
        deleted.append(thing)
    if certificate:
        missing = iot.exceptions.ResourceNotFoundException
        try:
            arn = iot.describe_certificate(certificateId=certificate)["certificateDescription"]["certificateArn"]
            for policy in iot.list_attached_policies(target=arn)["policies"]:
                iot.detach_policy(policyName=policy["policyName"], target=arn)
            iot.update_certificate(certificateId=certificate, newStatus="INACTIVE")
            iot.delete_certificate(certificateId=certificate, forceDelete=True)
            deleted.append(certificate[:12])
            print(f"aws: deleted certificate {certificate[:12]}", flush=True)
        except missing:
            pass
    return deleted


def environment(session) -> dict:
    """Environment for the existing AWS tools of this repository (they call the AWS CLI)."""
    credentials = session.get_credentials().get_frozen_credentials()
    return {"AWS_ACCESS_KEY_ID": credentials.access_key, "AWS_SECRET_ACCESS_KEY": credentials.secret_key,
            "AWS_SESSION_TOKEN": credentials.token, "AWS_DEFAULT_REGION": session.region_name,
            "AWS_CLI_USE_PYTHON_MODULE": "1"}
