''' manage remote users '''
import requests
from urllib.parse import urlparse

from fedireads import models
from fedireads.status import create_review


def get_or_create_remote_user(actor):
    ''' look up a remote user or add them '''
    try:
        return models.User.objects.get(actor=actor)
    except models.User.DoesNotExist:
        pass

    # TODO: also bring in the user's prevous reviews and books

    # load the user's info from the actor url
    response = requests.get(
        actor,
        headers={'Accept': 'application/activity+json'}
    )
    if not response.ok:
        response.raise_for_status()
    data = response.json()

    # the webfinger format for the username.
    actor_parts = urlparse(actor)
    username = '%s@%s' % (actor_parts.path.split('/')[-1], actor_parts.netloc)
    shared_inbox = data.get('endpoints').get('sharedInbox') if \
        data.get('endpoints') else None

    # throws a key error if it can't find any of these fields
    user = models.User.objects.create_user(
        username,
        '', '', # email and passwords are left blank
        actor=actor,
        name=data.get('name'),
        summary=data.get('summary'),
        inbox=data['inbox'], #fail if there's no inbox
        outbox=data['outbox'], # fail if there's no outbox
        shared_inbox=shared_inbox,
        # TODO: I'm never actually using this for remote users
        public_key=data.get('publicKey').get('publicKeyPem'),
        local=False,
        fedireads_user=data.get('fedireadsUser', False),
    )
    if user.fedireads_user:
        get_remote_reviews(user)
    return user


def get_remote_reviews(user):
    ''' ingest reviews by a new remote fedireads user '''
    outbox_page = user.outbox + '?page=true'
    response = requests.get(
        outbox_page,
        headers={'Accept': 'application/activity+json'}
    )
    data = response.json()
    for status in data['orderedItems']:
        if status.get('fedireadsType') == 'Review':
            book_id = status['inReplyToBook'].split('/')[-1]
            create_review(
                user,
                book_id,
                status['name'],
                status['content'],
                status['rating']
            )

