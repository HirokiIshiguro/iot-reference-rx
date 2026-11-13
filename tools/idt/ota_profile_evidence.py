"""Correlate CloudTrail records and verify live resources without changing them.

Input is a complete, privately obtained set of decoded CloudTrail events for one
run. The caller must authenticate the run, establish collection completeness,
serialize writers and independently check live resources before any action.
"""
import re


class EvidenceError(ValueError):
    """The supplied records cannot uniquely establish the requested linkage."""


def match_created_profile(events, *, run_actor_arn, certificate_arn, profile_name, before_names):
    """Return a candidate identity only when every recorded edge is unique.

    Select the profile name from the OTA update being recovered. One run can
    create multiple profiles with the same certificate.
    PutSigningProfile and StartSigningJob must use the same IoT service role;
    CreateOTAUpdate and ImportCertificate must use the authenticated run actor.
    This is correlation, not proof of collection completeness or current state.
    """
    certificate = (re.fullmatch(r'arn:aws:acm:([a-z0-9-]+):([0-9]{12}):certificate/[0-9a-fA-F-]{36}', certificate_arn)
                   if isinstance(certificate_arn, str) else None)
    if (not isinstance(events, list) or not isinstance(before_names, (list, tuple, set))
            or not isinstance(run_actor_arn, str) or not run_actor_arn
            or certificate is None or not isinstance(profile_name, str)
            or not re.fullmatch(r'[A-Za-z0-9_]{2,64}', profile_name)
            or any(not isinstance(name, str) for name in before_names)):
        raise EvidenceError('invalid evidence input')
    if profile_name in before_names:
        raise EvidenceError('preexisting profile')
    region, account = certificate.groups()
    relevant = {'ImportCertificate', 'CreateOTAUpdate', 'PutSigningProfile', 'StartSigningJob'}
    selected = []
    ids = set()
    for event in events:
        if not isinstance(event, dict):
            raise EvidenceError('invalid event')
        if event.get('eventName') not in relevant:
            continue
        eid = event.get('eventID')
        if not isinstance(eid, str) or not eid or eid in ids:
            raise EvidenceError('missing or duplicate event identity')
        ids.add(eid)
        if event.get('errorCode') or event.get('errorMessage'):
            continue
        if not isinstance(event.get('requestParameters'), dict) or not isinstance(event.get('responseElements'), dict):
            raise EvidenceError('incomplete event')
        selected.append(event)

    def actor(e):
        identity = e.get('userIdentity')
        return identity if isinstance(identity, dict) else {}

    def one(items):
        if len(items) != 1:
            raise EvidenceError('missing or ambiguous evidence')
        return items[0]

    imports = [e for e in selected if e['eventName'] == 'ImportCertificate'
               and e.get('eventSource') == 'acm.amazonaws.com'
               and actor(e).get('arn') == run_actor_arn
               and e['responseElements'].get('certificateArn') == certificate_arn]
    imported = one(imports)
    puts = [e for e in selected if e['eventName'] == 'PutSigningProfile'
            and e.get('eventSource') == 'signer.amazonaws.com'
            and e['requestParameters'].get('profileName') == profile_name]
    put = one(puts)
    signing_material = put['requestParameters'].get('signingMaterial')
    if (actor(put).get('invokedBy') != 'iot.amazonaws.com' or not isinstance(signing_material, dict)
            or signing_material.get('certificateArn') != certificate_arn):
        raise EvidenceError('profile actor or certificate mismatch')
    response = put['responseElements']
    version = response.get('profileVersion')
    arn = response.get('arn')
    if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9]{10}', version):
        raise EvidenceError('invalid profile version')
    expected_arn = f'arn:aws:signer:{region}:{account}:/signing-profiles/{profile_name}'
    if arn != expected_arn or response.get('profileVersionArn') != f'{arn}/{version}':
        raise EvidenceError('profile identity mismatch')

    def issuer(e):
        context = actor(e).get('sessionContext')
        if not isinstance(context, dict) or not isinstance(context.get('sessionIssuer'), dict):
            return None
        return context['sessionIssuer'].get('arn')

    service_role = issuer(put)
    if not isinstance(service_role, str) or not service_role.startswith(f'arn:aws:iam::{account}:role/'):
        raise EvidenceError('missing service role')
    starts = [e for e in selected if e['eventName'] == 'StartSigningJob'
              and e.get('eventSource') == 'signer.amazonaws.com'
              and actor(e).get('invokedBy') == 'iot.amazonaws.com'
              and issuer(e) == service_role
              and e['requestParameters'].get('profileName') == profile_name]
    start = one(starts)
    job = start['responseElements'].get('jobId')
    if not isinstance(job, str) or not job:
        raise EvidenceError('missing signing job identity')
    updates = []
    for event in selected:
        if (event['eventName'] != 'CreateOTAUpdate' or event.get('eventSource') != 'iot.amazonaws.com'
                or actor(event).get('arn') != run_actor_arn
                or event['requestParameters'].get('roleArn') != service_role):
            continue
        files = event['requestParameters'].get('files')
        if not isinstance(files, list):
            raise EvidenceError('incomplete OTA files')
        for entry in files:
            try:
                param = entry['codeSigning']['startSigningJobParameter']
                if (param['signingProfileName'] == profile_name
                        and param['signingProfileParameter']['certificateArn'] == certificate_arn):
                    updates.append(event)
            except (KeyError, TypeError):
                continue
    update = one(updates)
    update_id = update['requestParameters'].get('otaUpdateId')
    update_response = update['responseElements']
    if (not isinstance(update_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', update_id)
            or update_response.get('otaUpdateId') != update_id
            or update_response.get('otaUpdateArn') != f'arn:aws:iot:{region}:{account}:otaupdate/{update_id}'):
        raise EvidenceError('OTA update identity mismatch')
    return {'profileName': profile_name, 'arn': arn, 'profileVersion': version,
            'profileVersionArn': response['profileVersionArn'], 'certificateArn': certificate_arn,
            'otaUpdateId': update_id, 'signingJobId': job,
            'eventIds': {event['eventName']: event['eventID'] for event in (imported, put, start, update)}}


def verify_live_profile(candidate, *, iot, signer, account, region, thing_arn, iot_job_id):
    """Read and verify one correlated candidate; never authorizes a mutation.

    Clients must already be authenticated. API failures propagate to the caller.
    A successful result is a snapshot and does not establish collection completeness.
    """
    if (not isinstance(candidate, dict) or not isinstance(account, str) or not re.fullmatch(r'[0-9]{12}', account)
            or not isinstance(region, str) or not re.fullmatch(r'[a-z0-9-]+', region)
            or not isinstance(thing_arn, str)
            or not re.fullmatch(rf'arn:aws:iot:{re.escape(region)}:{account}:thing/[^/]+', thing_arn)
            or not isinstance(iot_job_id, str) or not iot_job_id
            or iot.meta.region_name != region or signer.meta.region_name != region):
        raise EvidenceError('invalid live verification scope')
    try:
        name = candidate['profileName']
        version = candidate['profileVersion']
        cert = candidate['certificateArn']
        update_id = candidate['otaUpdateId']
        signing_id = candidate['signingJobId']
        profile_arn = f'arn:aws:signer:{region}:{account}:/signing-profiles/{name}'
        if (not all(isinstance(value, str) and value for value in (name, version, cert, update_id, signing_id))
                or candidate['arn'] != profile_arn
                or candidate['profileVersionArn'] != f'{profile_arn}/{version}'
                or not re.fullmatch(rf'arn:aws:acm:{re.escape(region)}:{account}:certificate/[0-9a-fA-F-]{{36}}', cert)):
            raise EvidenceError('candidate identity mismatch')
        update = iot.get_ota_update(otaUpdateId=update_id)['otaUpdateInfo']
        files = update['otaUpdateFiles']
        if (update['otaUpdateId'] != update_id
                or update['otaUpdateArn'] != f'arn:aws:iot:{region}:{account}:otaupdate/{update_id}'
                or update['targets'] != [thing_arn]
                or update['awsIotJobId'] != iot_job_id
                or update['awsIotJobArn'] != f'arn:aws:iot:{region}:{account}:job/{iot_job_id}'
                or not isinstance(files, list) or len(files) != 1):
            raise EvidenceError('live OTA identity mismatch')
        signing = files[0]['codeSigning']
        if signing['awsSignerJobId'] != signing_id:
            raise EvidenceError('live OTA signing mismatch')
        job = signer.describe_signing_job(jobId=signing_id)
        if (job['jobId'] != signing_id or job['jobOwner'] != account
                or job['profileName'] != name or job['profileVersion'] != version
                or job['signingMaterial']['certificateArn'] != cert):
            raise EvidenceError('live signing job mismatch')
    except (KeyError, TypeError, AttributeError):
        raise EvidenceError('incomplete live evidence') from None
    return {'otaUpdateId': update_id, 'awsIotJobId': iot_job_id, 'signingJobId': signing_id}
