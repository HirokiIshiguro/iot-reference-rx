"""Compose private run evidence without authorizing any recovery action."""
import re

from tools.idt.ota_profile_evidence import EvidenceError, match_created_job, verify_live_profile


def inspect_candidate(store, original, expected, *, role_arn, certificate_arn, profile_name,
                      events, iot, signer):
    """Inspect one candidate using caller-authenticated private run evidence.

    The caller must authenticate the recovery job, serialize writers, verify
    that the configured role belongs to the original run and supply a complete
    CloudTrail collection from trusted private evidence.
    This snapshot proves neither collection completeness nor permission to act.
    """
    record, _, version = store.inspect(original)
    if (not isinstance(expected, tuple) or len(expected) != 2
            or (record['request_id'], version) != expected
            or record['state'] not in ('ACTIVE', 'UNKNOWN')
            or original.project_id != '38'):
        raise EvidenceError('admission generation or state mismatch')
    intent = record.get('profile_intent')
    if not intent or certificate_arn not in intent['certificates']:
        raise EvidenceError('missing recorded certificate intent')
    role = (re.fullmatch(rf'arn:aws:iam::{original.account}:role/(?:[A-Za-z0-9+=,.@_-]+/)*([A-Za-z0-9+=,.@_-]+)', role_arn)
            if isinstance(role_arn, str) else None)
    if role is None:
        raise EvidenceError('invalid original role')
    actor = f'arn:aws:sts::{original.account}:assumed-role/{role.group(1)}/gitlab38-{original.job_id}'
    candidate = match_created_job(events, run_actor_arn=actor, certificate_arn=certificate_arn,
                                  profile_name=profile_name,
                                  before_names=[item['profileName'] for item in intent['before']])
    live = verify_live_profile(candidate, iot=iot, signer=signer, account=original.account,
                               region=original.region, thing_arn=candidate['thingArn'],
                               iot_job_id=candidate['iotJobId'])
    return {'admission': expected, 'candidate': candidate, 'live': live}
