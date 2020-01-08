import sys
import logging

import utils.smtp_client as smtp_client
import reconcile.queries as queries

from utils.state import State

QONTRACT_INTEGRATION = 'email-sender'


def collect_to(to):
    """Collect audience to send email to from to object

    Arguments:
        to {dict} -- AppInterfaceEmailAudience_v1 object

    Raises:
        AttributeError: Unknown alias

    Returns:
        set -- Audience to send email to
    """
    audience = set()

    aliases = to.get('aliases')
    if aliases:
        for alias in aliases:
            if alias == 'all-users':
                users = queries.get_users()
                to['users'] = users
            elif alias == 'all-service-owners':
                services = queries.get_apps()
                to['services'] = services
            else:
                raise AttributeError(f"unknown alias: {alias}")

    services = to.get('services')
    if services:
        for service in services:
            service_owners = service.get('serviceOwners')
            if not service_owners:
                continue

            for service_owner in service_owners:
                audience.add(service_owner['email'])

    clusters = to.get('clusters')
    if clusters:
        # TODO: implement this
        for cluster in clusters:
            pass

    namespaces = to.get('namespaces')
    if namespaces:
        # TODO: implement this
        for namespace in namespaces:
            pass

    aws_accounts = to.get('aws_accounts')
    if aws_accounts:
        for account in aws_accounts:
            account_owners = account.get('accountOwners')
            if not account_owners:
                continue

            for account_owner in account_owners:
                audience.add(account_owner['email'])

    roles = to.get('roles')
    if roles:
        for role in roles:
            users = role.get('users')
            if not users:
                continue

            for user in users:
                audience.add(user['org_username'])

    users = to.get('users')
    if users:
        for user in users:
            audience.add(user['org_username'])

    return audience


def run(dry_run=False):
    settings = queries.get_app_interface_settings()
    accounts = queries.get_aws_accounts()
    state = State(
        integration=QONTRACT_INTEGRATION,
        accounts=accounts,
        settings=settings
    )
    emails = queries.get_app_interface_emails()

    # validate no 2 emails have the same name
    email_names = set([e['name'] for e in emails])
    if len(emails) != len(email_names):
        logging.error('email names must be unique.')
        sys.exit(1)

    emails_to_send = [e for e in emails if not state.exists(e['name'])]

    # validate that there is only 1 mail to send
    # this is a safety net in case state is lost
    # the solution to such loss is to delete all emails from app-interface
    if len(emails_to_send) > 1:
        logging.error('can only send one email at a time.')
        sys.exit(1)

    for email in emails_to_send:
        logging.info(['send_email', email['name'], email['subject']])

        if not dry_run:
            names = collect_to(email['to'])
            subject = email['subject']
            body = email['body']
            smtp_client.send_mail(names, subject, body, settings=settings)
            state.add(email['name'])
