import boto3
import botocore
from django.core.urlresolvers import reverse
import hashlib
import hmac

s3 = boto3.client(
    's3',
    config=botocore.client.Config(signature_version='s3v4'),
    region_name='eu-west-1'
)
GIT_LFS_BUCKET = 'touchsurgery-git-lfs-object-store'


class GitLFSServer(object):
    content_type = 'application/vnd.git-lfs+json'

    def __init__(self, secret):
        self.secret = secret

    def handle(self, request, host):
        objects = [
            GitLFSObject(o['oid'], o['size'], self).as_dict(
                host,
                request['operation']
            ) for o in request['objects']
        ]

        response = {
            'transfer': 'basic',
            'objects': objects
        }
        return response

    def verify(self, request, hmac):
        glfs_object = GitLFSObject(
            request.get('oid'),
            request.get('size')
        )
        hmac_matches_and_object_exists = (
            glfs_object.hmac() == hmac
            and glfs_object.exists()
        )
        if hmac_matches_and_object_exists:
            return True

        return False


class GitLFSObject(object):

    LINK_EXPIRY = 3600

    def __init__(self, oid, size=None, server):
        self._server = server
        self.size = size
        self.oid = oid
        self.sharded_key = '{}/{}/{}'.format(oid[0:2], oid[2:4], oid)

    def exists(self):
        return object_exists(self.oid)

    def _action(self, href):
        return {
            'href': href,
            'header': {},
            'expires_in': self.LINK_EXPIRY
        }

    def error(self, code, message):
        return {
            'code': code,
            'message': message
        }

    def download(self):
        return self._action(signed_get_request(self.oid))

    def upload(self):
        return self._action(signed_put_request(self.oid))

    def verify(self, hostname):
        return self._action(verify_request(self.hmac(), hostname))

    def hmac(self):
        return hmac.new(
            str(self._server.secret),
            '{}.{}'.format(self.oid, self.size),
            hashlib.sha256
        ).hexdigest()

    def as_dict(self, hostname, operation='download'):
        object_dict = {
            'oid': self.oid,
            'size': self.size,
            'authenticated': True,
            'actions': {}
        }
        if operation == 'download':
            if self.exists():
                object_dict['actions']['download'] = self.download()
            else:
                object_dict['error'] = self.error(
                    404,
                    'object does not exist'
                )
                object_dict.pop('actions')
        elif operation == 'upload':
            if self.exists():
                object_dict.pop('actions')
            else:
                object_dict['actions']['upload'] = self.upload()
                object_dict['actions']['verify'] = self.verify(hostname)

        return object_dict


def sharded_key(oid):
    return '{}/{}/{}'.format(oid[0:2], oid[2:4], oid)


def object_exists(oid):
    try:
        boto3.resource('s3').Object(
            GIT_LFS_BUCKET, sharded_key(oid)
        ).load()
        return True
    except botocore.exceptions.ClientError as exc:
        if exc.response['Error']['Code'] == '404':
            return False
        if exc.response['Error']['Code'] == '403':
            return True
        else:
            raise


def signed_request(oid, http_method):
    return s3.generate_presigned_url(
        ClientMethod={
            'PUT': 'put_object',
            'GET': 'get_object'
        }[http_method],
        Params={
            'Key': sharded_key(oid),
            'Bucket': GIT_LFS_BUCKET
        },
        ExpiresIn=3600,
        HttpMethod=http_method
    )


def signed_put_request(oid):
    return signed_request(oid, 'PUT')


def signed_get_request(oid):
    return signed_request(oid, 'GET')


def verify_request(hmac, hostname):
    return 'https://{}{}?h={}'.format(
        hostname,
        reverse('git_lfs:verify'),
        hmac
    )
