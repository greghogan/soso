"""Native Azure SDK contract checks; no credentials or live service calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from soso.assets import asset_azure as azure
from soso.assets.asset_storage import parse


class AzureNativeTests(unittest.TestCase):
    def test_conditional_upload_raw_download_and_nonpurging_delete(self):
        client = MagicMock()
        blob = client.get_blob_client.return_value
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'image'
            path.write_bytes(b'exact')
            with patch.object(azure, 'credential') as identity, patch.object(azure, 'service_client') as service:
                service.return_value.__enter__.return_value = client
                azure.transfer(parse('az://sosobackup/originals/path'), 'put', 'a'*64, path)
                self.assertEqual(blob.upload_blob.call_args.kwargs, dict(blob_type='BlockBlob', overwrite=False, if_none_match='*'))
                azure.transfer(parse('az://sosobackup/originals/path'), 'get', 'a'*64, path)
                blob.download_blob.assert_called_once_with(decompress=False)
                azure.transfer(parse('az://sosobackup/originals/path'), 'delete', 'a'*64)
                blob.delete_blob.assert_called_once_with(retry_total=0)

    def test_structured_conflict_only_and_redaction(self):
        from azure.core.exceptions import HttpResponseError
        for code in ('BlobAlreadyExists', 'ConditionNotMet', 'AuthorizationFailure'):
            error = HttpResponseError('secret diagnostic')
            error.error_code = code
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'image'; path.write_bytes(b'exact')
                with patch.object(azure, 'credential'), patch.object(azure, 'service_client') as service:
                    service.return_value.__enter__.return_value.get_blob_client.return_value.upload_blob.side_effect = error
                    with self.assertRaises(RuntimeError) as raised:
                        azure.transfer(parse('az://sosobackup/originals'), 'put', 'a'*64, path)
                    self.assertNotIn('secret', str(raised.exception))
                    self.assertEqual(str(raised.exception), code if code != 'AuthorizationFailure' else 'Azure request failed; check Entra authentication, permissions and connectivity.')

    def test_only_canonical_endpoint_and_token_credentials(self):
        with patch('azure.storage.blob.BlobServiceClient') as client:
            identity = object()
            azure.service_client('sosobackup', identity)
            client.assert_called_once_with('https://sosobackup.blob.core.windows.net', credential=identity)

class AzureManagementTests(unittest.TestCase):
    def test_native_read_state_uses_wire_models_and_all_historical_pages(self):
        from azure.mgmt.storage import models as m
        from azure.mgmt.resource.subscriptions.models import Subscription
        from soso.assets import asset_setup_azure as setup
        from unittest.mock import Mock
        c = setup.configuration('az://sosobackup/originals/path', '1'*8+'-'+ '1'*4+'-'+ '1'*4+'-'+ '1'*4+'-'+ '1'*12, '2'*8+'-'+ '2'*4+'-'+ '2'*4+'-'+ '2'*4+'-'+ '2'*12, 'soso', 'eastus')
        subscription = Subscription({'subscriptionId': c['subscription'], 'tenantId': c['tenant']})
        account = m.StorageAccount({'id':c['scope'], 'location':'eastus', 'properties': {'allowBlobPublicAccess':False, 'allowSharedKeyAccess':False, 'supportsHttpsTrafficOnly':True, 'minimumTlsVersion':'TLS1_2', 'encryption':{'services':{'blob':{'enabled':True}}}}})
        policy = m.ManagementPolicy({'properties':{'policy':{'rules':[]}}})
        service = m.BlobServiceProperties({'properties':{'isVersioningEnabled':False, 'deleteRetentionPolicy':{'enabled':False}, 'containerDeleteRetentionPolicy':{'enabled':False}}})
        with patch.object(azure, 'credential'), patch.object(azure, 'service_client') as blobs, patch('azure.mgmt.storage.StorageManagementClient') as storage, patch('azure.mgmt.resource.subscriptions.SubscriptionClient') as subscriptions:
            subscriptions.return_value.__enter__.return_value.subscriptions.get.return_value = subscription
            mgmt = storage.return_value.__enter__.return_value
            mgmt.storage_accounts.get_properties.return_value = account
            mgmt.management_policies.get.return_value = policy
            mgmt.blob_services.get_service_properties.return_value = service
            container = blobs.return_value.__enter__.return_value.get_container_client.return_value
            container.get_container_properties.return_value = {'name':'originals', 'public_access':None}
            container.list_blobs.return_value = iter([])
            self.assertTrue(setup.verify(c))
            container.list_blobs.assert_called_once_with(name_starts_with='path/', include=['deleted', 'snapshots', 'versions'])
