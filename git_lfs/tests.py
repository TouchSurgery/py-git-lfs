from django.core.urlresolvers import reverse
import botocore
import hashlib
import json
from mock import patch
import requests
from rest_framework.test import APITestCase

from touchsurgery.apps.core import factories as core_factories
from touchsurgery.apps.git_lfs.lfs import (
    GitLFSServer,
    GitLFSObject,
    signed_get_request,
    signed_put_request,
    object_exists
)

REQUEST_HEADERS = {
    'ACCEPT': GitLFSServer.content_type
}


class TestGitLFSNoMock(APITestCase):

    def DONTtest_object_roundtrip(self):
        # turned off normally because it's too slow
        # But handy to keep for debugging
        content = 'test'
        oid = hashlib.sha256(content).hexdigest()

        put = requests.put(signed_put_request(oid), data=content)
        get = requests.get(signed_get_request(oid))
        exists = object_exists(oid)

        self.assertEqual(
            put.status_code,
            200,
            'PUT failed {}, content was: {}'.format(
                put.status_code, put.content
            )
        )
        self.assertEqual(
            get.status_code,
            200,
            'GET failed with {}, content was: {}'.format(
                get.status_code, get.content
            )
        )
        self.assertTrue(exists)


@patch('touchsurgery.apps.git_lfs.lfs.signed_get_request')
@patch('touchsurgery.apps.git_lfs.lfs.signed_put_request')
@patch('touchsurgery.apps.git_lfs.lfs.object_exists')
class TestGitLFS(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.batch_endpoint = reverse('git_lfs:batch')
        cls.verify_endpoint = reverse('git_lfs:verify')

    def setUp(self):
        self.user = core_factories.UserFactory()
        self.client.force_authenticate(self.user)

    def test_batch_upload_operation(self, mock_exists, mock_put, mock_get):
        mock_exists.return_value = False
        mock_put.return_value = 'signed_put_request'
        with patch('touchsurgery.apps.git_lfs.lfs.verify_request') as mv:
            mv.return_value = 'verify_link'
            response = self.client.post(
                self.batch_endpoint,
                json.dumps({
                    'operation': 'upload',
                    'transfers': ['basic'],
                    'objects': [
                        {
                            'oid': '12345',
                            'size': 500
                        }
                    ]
                }),
                content_type=GitLFSServer.content_type,
                **REQUEST_HEADERS
            )

        self.assertEqual(
            response.json,
            {
                'transfer': 'basic',
                'objects': [
                    {
                        'oid': '12345',
                        'size': 500,
                        'authenticated': True,
                        'actions': {
                            'upload': {
                                'href': 'signed_put_request',
                                'header': {},
                                'expires_in': 3600,
                            },
                            'verify': {
                                'href': 'verify_link',
                                'header': {},
                                'expires_in': 3600,
                            },
                        }
                    }
                ]
            }
        )

    def test_upload_operation_when_object_exists(
        self, mock_exists, mock_put, mock_get
    ):
        self.maxDiff = None
        mock_exists.return_value = True

        response = self.client.post(
            self.batch_endpoint,
            json.dumps({
                'operation': 'upload',
                'transfers': ['basic'],
                'objects': [
                    {
                        'oid': '12345',
                        'size': 500
                    }
                ]
            }),
            content_type=GitLFSServer.content_type,
            **REQUEST_HEADERS
        )

        self.assertEqual(
            response.json,
            {
                'transfer': 'basic',
                'objects': [
                    {
                        'oid': '12345',
                        'size': 500,
                        'authenticated': True,
                    }
                ]
            }
        )


    def test_verify_when_object_exists(self, mock_exists, mock_put, mock_get):
        mock_exists.return_value = True
        oid, size = '12345', 500
        hmac = GitLFSObject(oid, size).hmac()
        response = self.client.post(
            self.verify_endpoint + '?h=' + hmac,
            json.dumps({
                'oid': oid,
                'size': size
            }),
            content_type=GitLFSServer.content_type,
            **REQUEST_HEADERS
        )

        self.assertEqual(response.status_code, 200)

    def test_verify_when_no_object(self, mock_exists, mock_put, mock_get):
        mock_exists.return_value = False
        oid, size = '12345', 500
        hmac = GitLFSObject(oid, size).hmac()
        response = self.client.post(
            self.verify_endpoint + '?h=' + hmac,
            json.dumps({
                'oid': oid,
                'size': size
            }),
            content_type=GitLFSServer.content_type,
            **REQUEST_HEADERS
        )

        self.assertEqual(response.status_code, 404)

    def test_verify_with_bad_hmac(self, mock_exists, mock_put, mock_get):
        mock_exists.return_value = True
        oid, size = '12345', 500
        response = self.client.post(
            self.verify_endpoint + '?h=' + 'badhmac',
            json.dumps({
                'oid': oid,
                'size': size
            }),
            content_type=GitLFSServer.content_type,
            **REQUEST_HEADERS
        )

        self.assertEqual(response.status_code, 404)

    def test_batch_download_operation(self, mock_exists, mock_put, mock_get):
        mock_get.return_value = 'signed_get_request'

        def mocked_exists(oid):
            if oid == '12345':
                return False
            return True
        mock_exists.side_effect = mocked_exists

        self.maxDiff = None
        response = self.client.post(
            self.batch_endpoint,
            json.dumps({
                'operation': 'download',
                'transfers': ['basic'],
                'objects': [
                    {
                        'oid': '54321',
                        'size': 500
                    },
                    {
                        'oid': '12345',
                        'size': 500
                    }
                ]

            }),
            content_type=GitLFSServer.content_type,
            **REQUEST_HEADERS
        )

        self.assertEqual(
            response.json,
            {
                'transfer': 'basic',
                'objects': [
                    {
                        'oid': '54321',
                        'size': 500,
                        'authenticated': True,
                        'actions': {
                            'download': {
                                'href': 'signed_get_request',
                                'header': {},
                                'expires_in': 3600,
                            },
                        }
                    },
                    {
                        'oid': '12345',
                        'size': 500,
                        'authenticated': True,
                        'error': {
                            'code': 404,
                            'message': 'object does not exist'
                        },
                    }
                ]
            }
        )


class TestObjectExists(APITestCase):

    @patch('touchsurgery.apps.git_lfs.lfs.boto3.resource')
    def test_object_exists_when_not_there(self, mock_resource):
        mock_Object = mock_resource.return_value.Object
        mock_Object.side_effect = botocore.exceptions.ClientError(
            {'Error': {'Code': '404', 'Message': 'Halp'}},
            'PutObject'
        )

        self.assertFalse(object_exists('an-oid'))

    @patch('touchsurgery.apps.git_lfs.lfs.boto3.resource')
    def test_object_exists_when_present_but_inaccesible(self, mock_resource):
        mock_Object = mock_resource.return_value.Object

        mock_Object.side_effect = botocore.exceptions.ClientError(
            {'Error': {'Code': '403', 'Message': 'Halp'}},
            'PutObject'
        )

        self.assertTrue(object_exists('an-oid'))

    @patch('touchsurgery.apps.git_lfs.lfs.boto3.resource')
    def test_object_exists_with_other_exceptions(self, mock_resource):
        mock_Object = mock_resource.return_value.Object
        mock_Object.side_effect = botocore.exceptions.ClientError(
            {'Error': {'Code': '500', 'Message': 'Halp'}},
            'PutObject'
        )

        with self.assertRaises(botocore.exceptions.ClientError):
            object_exists('an-oid')

    @patch('touchsurgery.apps.git_lfs.lfs.boto3.resource')
    def test_object_exists_when_accessible_object_there(self, mock_resource):
        self.assertTrue(object_exists('an-oid'))
