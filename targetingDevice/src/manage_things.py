"""Setting everything up for the Device"""
import os
import json
import time
import uuid
import logging
import argparse
import datetime
import threading
from boto3.session import Session
from botocore.exceptions import ClientError
from random import choice
from string import lowercase
from laser_guidance_core import *

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

policy_name_key = "lg_policy"
policy_arn_key = "lg_policy_arn"
thing_name_template = "lg_thing_{0}"


def certs_exist():
    path = os.getcwd() + '/' + lg_cfg_dir
    files = os.listdir(path)
    if thing_name_template.format(0) + ".pem" in files:
        # if certs created previously there will always be a zero'th pem file
        log.info("Previously created certs exist. Please 'clean' before creating.")
        return True

    return False


def _create_and_attach_policy(region, thing_name, thing_cert_arn, cli):
    # Create and attach to the principal/certificate the minimal action
    # privileges Thing policy that allows publish and subscribe
    tp = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                # "iot:*"
                "iot:Connect",
                "iot:Publish",
                "iot:Receive",
                "iot:Subscribe"
            ],
            "Resource": [
                "arn:aws:iot:{0}:*:*".format(region)
            ]
        }]
    }

    iot = get_iot_session(region, cli.profile_name)
    policy_name = 'policy-{0}'.format(thing_name)
    policy = json.dumps(tp)
    log.debug('[_create_and_attach_policy] policy:{0}'.format(policy))
    p = iot.create_policy(
        policyName=policy_name,
        policyDocument=policy
    )
    log.debug("[_create_and_attach_policy] Created Policy: {0}".format(
        p['policyName']))

    iot.attach_principal_policy(
        policyName=policy_name, principal=thing_cert_arn)
    log.debug("[_create_and_attach_policy] Attached {0} to {1}".format(
        policy_name, thing_cert_arn))

    return p['policyName'], p['policyArn']


def create_things(cli):
    """
    Create and activate a specified number of Things in the AWS IoT Service.
    """
    init(cli)
    region = cli.region
    iot = get_iot_session(region, cli.profile_name)
    count = cli.thing_count
    things = list()
    if certs_exist():
        return

    if count == 0 or count > 1:
        log.info("[create_things] LaserGuidance creating {0} things".format(count))
    else:
        log.info("[create_things] LaserGuidance creating {0} thing".format(count))

    i = 0
    while i < count:
        ###
        # This is portion of the loop is the core of the `create` command
        # generate a numbered thing name
        t_name = thing_name_template.format(i)
        # Create a Key and Certificate in the AWS IoT Service per Thing
        keys_cert = iot.create_keys_and_certificate(setAsActive=True)
        # Create a named Thing in the AWS IoT Service
        iot.create_thing(thingName=t_name)
        # Attach the previously created Certificate to the created Thing
        iot.attach_thing_principal(
            thingName=t_name, principal=keys_cert['certificateArn'])
        # This is the end of the core of the `create` command
        ###

        things.append({t_name: keys_cert})
        cert_arn = things[i][t_name]['certificateArn']
        log.info("Thing:'{0}' associated with cert:'{1}'".format(
            t_name, cert_arn))

        _create_and_attach_policy(
            cli.region,
            t_name, cert_arn,
            cli
        )

        # Save all the Key and Certificate files locally for future cleanup
        # ..could be added to Keyring later (https://github.com/jaraco/keyring)
        try:
            certname = cfg_dir + t_name + ".pem"
            public_key_file = cfg_dir + t_name + ".pub"
            private_key_file = cfg_dir + t_name + ".prv"
            with open(certname, "w") as pem_file:
                # out_file.write(things[i][thing_name])
                pem = things[i][t_name]['certificatePem']
                pem_file.write(pem)
                log.info("Thing Name: {0} and PEM file: {1}".format(
                    t_name, certname))

            with open(public_key_file, "w") as pub_file:
                pub = things[i][t_name]['keyPair']['PublicKey']
                pub_file.write(pub)
                log.info("Thing Name: {0} Public Key File: {1}".format(
                    t_name, public_key_file))

            with open(private_key_file, "w") as prv_file:
                prv = things[i][t_name]['keyPair']['PrivateKey']
                prv_file.write(prv)
                log.info("Thing Name: {0} Private Key File: {1}".format(
                    t_name, private_key_file))

            update_things_config(things)
        except OSError as ose:
            log.error('OSError while writing an LaserGuidance file. {0}'.format(ose))
        i += 1
        # end 'while' - if there's more, do it all again

    log.info(
        "[create_things] LaserGuidance created {0} things in region:'{1}'.".format(
            i, region))

def clean_up(cli):
    """
    Clean up all Things previously created in the AWS IoT Service and files
    stored locally.
    """
    init(cli)
    log.info("[clean_up] LaserGuidance is cleaning up...")
    iot = get_iot_session(cli.region, cli.profile_name)
    only_local = cli.only_local

    if not only_local:
        lg = get_lg_config()
        things = get_things_config()
        if things is None:
            log.info('[clean_up] There is nothing to clean up.')
            return

        i = 0
        for t in things:
            # for each Thing in the configuration file
            thing_name = thing_name_template.format(i)
            thing = t[thing_name]
            # First use the DetachPrincipalPolicy API to detach all policies.
            if policy_name_key in thing:
                try:
                    log.debug('[clean_up] detaching principal policy:{0}'.format(
                        thing[policy_name_key]))
                    iot.detach_principal_policy(
                        policyName=thing[policy_name_key],
                        principal=thing['certificateArn']
                    )
                    # Next, use the DeletePolicy API to delete the policy from
                    # the service
                    log.debug('[clean_up] deleting policy:{0}'.format(
                        thing[policy_name_key]))
                    iot.delete_policy(
                        policyName=thing[policy_name_key]
                    )
                except ClientError as ce:
                    log.info(
                        '[clean_up] could not detach, or delete policy:{0} from cert:{1}'.format(
                            thing[policy_name_key], thing['certificateArn']))
                    log.debug('[clean_up] {0}'.format(ce))

            else:
                log.info('[clean_up] could not find policy to clean')

            # Next, use the UpdateCertificate API to set the certificate to the
            # INACTIVE status.
            try:
                log.debug('[clean_up] deactivating certificate:{0}'.format(
                    thing['certificateId']))
                iot.update_certificate(
                    certificateId=thing['certificateId'],
                    newStatus='INACTIVE'
                )

                # Next, use the DetachThingPrincipal API to detach the
                # Certificate from the Thing.
                log.debug('[clean_up] detaching certificate:{0} from thing:{1}'.format(
                    thing['certificateArn'], thing_name))
                iot.detach_thing_principal(
                    thingName=thing_name,
                    principal=thing['certificateArn']
                )
                time.sleep(1)

                # Next, use the DeleteCertificate API to delete each created
                # Certificate.
                log.debug('[clean_up] deleting certificate:{0}'.format(
                    thing['certificateId']))
                iot.delete_certificate(certificateId=thing['certificateId'])

                # Last, delete policy
                policy_name = 'policy-{0}'.format(thing_name)
                iot.delete_policy(
                    policyName=policy_name
                )

            except ClientError as ce:
                log.info('[clean_up] could not find, detach, or delete certificate:{0}'.format(
                    thing['certificateId']))
                log.debug('[clean_up] {0}'.format(ce))

            # Then, use the DeleteThing API to delete each created Thing
            log.debug('[clean_up] deleting thing:{0}'.format(thing_name))
            iot.delete_thing(thingName=thing_name)
            log.info(
                '[clean_up] Cleaned things, policies, & certs for:{0}'.format(
                    thing_name))
            i += 1

        log.info(
            '[clean_up] Cleaned {0} things, policies, & certs.. cleaning locally.'.format(i))
        # end of IF

    # Finally, delete the locally created files
    log.debug('[clean_up] local files')
    path = os.getcwd() + '/' + lg_cfg_dir
    files = os.listdir(path)
    for f in files:
        if not f == lg_file:
            log.debug("[clean_up] File found: {0}".format(f))
            os.remove(path + '/' + f)

    log.info("[clean_up] LaserGuidance has completed cleaning up in region:{0}".format(
        cli.region))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Simple way to generate IoT messages for multiple Things.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--region', dest='region', help='The AWS region to use.',
                        default='us-west-2')
    parser.add_argument('--profile', dest='profile_name',
                        help='The AWS CLI profile to use.')
    subparsers = parser.add_subparsers()

    create = subparsers.add_parser(
        'create',
        description='Create a number of Things that will interact with AWS IoT')
    create.add_argument('thing_count', nargs='?', default=1, type=int,
                        help="How many 'Things' to create.")
    create.set_defaults(func=create_things)

    clean = subparsers.add_parser(
        'clean',
        description='Clean up artifacts used to communicate with AWS IoT')
    clean.set_defaults(func=clean_up)
    clean.add_argument(
        '--force', '--only-local', dest='only_local',
        action='store_true',
        help='WARNING - Force clean only the locally stored LG files. LG will NOT clean up the resources created in the AWS IoT service.')


    args = parser.parse_args()
    args.func(args)
