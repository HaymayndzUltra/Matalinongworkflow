"""
Storage Adapters for Audit Export
Supports S3, Google Cloud Storage, Azure Blob, and Local filesystem
"""

import os
import json
import hashlib
from typing import Dict, Any, Optional, BinaryIO
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StorageAdapter(ABC):
    """Abstract base class for storage adapters"""
    
    @abstractmethod
    def upload(self, file_path: Path, remote_path: str) -> Dict[str, Any]:
        """Upload file to storage"""
        pass
    
    @abstractmethod
    def download(self, remote_path: str, local_path: Path) -> bool:
        """Download file from storage"""
        pass
    
    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        """Check if file exists in storage"""
        pass
    
    @abstractmethod
    def get_signed_url(self, remote_path: str, expiry_hours: int = 24) -> str:
        """Get signed URL for temporary access"""
        pass
    
    @abstractmethod
    def delete(self, remote_path: str) -> bool:
        """Delete file from storage (if not WORM protected)"""
        pass
    
    @abstractmethod
    def set_worm(self, remote_path: str, retention_days: int) -> bool:
        """Set WORM (Write Once Read Many) protection"""
        pass


class LocalStorageAdapter(StorageAdapter):
    """Local filesystem storage adapter"""
    
    def __init__(self, base_path: str = "./audit_storage"):
        """Initialize local storage adapter"""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.worm_registry = self.base_path / ".worm_registry.json"
        self._load_worm_registry()
    
    def _load_worm_registry(self):
        """Load WORM protection registry"""
        if self.worm_registry.exists():
            with open(self.worm_registry, 'r') as f:
                self.worm_files = json.load(f)
        else:
            self.worm_files = {}
    
    def _save_worm_registry(self):
        """Save WORM protection registry"""
        with open(self.worm_registry, 'w') as f:
            json.dump(self.worm_files, f, indent=2)
    
    def upload(self, file_path: Path, remote_path: str) -> Dict[str, Any]:
        """Copy file to local storage"""
        try:
            dest_path = self.base_path / remote_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                content = src.read()
                dst.write(content)
            
            # Calculate checksum
            checksum = hashlib.sha256(content).hexdigest()
            
            return {
                "success": True,
                "path": str(dest_path),
                "size": dest_path.stat().st_size,
                "checksum": checksum,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to upload to local storage: {e}")
            return {"success": False, "error": str(e)}
    
    def download(self, remote_path: str, local_path: Path) -> bool:
        """Copy file from local storage"""
        try:
            src_path = self.base_path / remote_path
            
            if not src_path.exists():
                return False
            
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(src_path, 'rb') as src, open(local_path, 'wb') as dst:
                dst.write(src.read())
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to download from local storage: {e}")
            return False
    
    def exists(self, remote_path: str) -> bool:
        """Check if file exists"""
        return (self.base_path / remote_path).exists()
    
    def get_signed_url(self, remote_path: str, expiry_hours: int = 24) -> str:
        """Get file path (no signing for local storage)"""
        return f"file://{self.base_path / remote_path}"
    
    def delete(self, remote_path: str) -> bool:
        """Delete file if not WORM protected"""
        try:
            file_path = str(self.base_path / remote_path)
            
            # Check WORM protection
            if file_path in self.worm_files:
                retention_end = datetime.fromisoformat(
                    self.worm_files[file_path]["retention_end"]
                )
                if datetime.now() < retention_end:
                    logger.warning(f"Cannot delete WORM protected file: {remote_path}")
                    return False
            
            (self.base_path / remote_path).unlink()
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete from local storage: {e}")
            return False
    
    def set_worm(self, remote_path: str, retention_days: int) -> bool:
        """Set WORM protection on file"""
        try:
            file_path = str(self.base_path / remote_path)
            
            if not (self.base_path / remote_path).exists():
                return False
            
            # Set file to read-only
            os.chmod(file_path, 0o444)
            
            # Register WORM protection
            retention_end = datetime.now() + timedelta(days=retention_days)
            self.worm_files[file_path] = {
                "protected_at": datetime.now().isoformat(),
                "retention_end": retention_end.isoformat(),
                "retention_days": retention_days
            }
            self._save_worm_registry()
            
            logger.info(f"WORM protection set for {remote_path} until {retention_end}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set WORM protection: {e}")
            return False


class S3StorageAdapter(StorageAdapter):
    """AWS S3 storage adapter"""
    
    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """Initialize S3 storage adapter"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            self.bucket_name = bucket_name
            self.region = region
            
            # Initialize S3 client
            if aws_access_key_id and aws_secret_access_key:
                self.s3_client = boto3.client(
                    's3',
                    region_name=region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
            else:
                # Use default credentials
                self.s3_client = boto3.client('s3', region_name=region)
            
            self.ClientError = ClientError
            
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
    
    def upload(self, file_path: Path, remote_path: str) -> Dict[str, Any]:
        """Upload file to S3"""
        try:
            # Upload file
            self.s3_client.upload_file(
                str(file_path),
                self.bucket_name,
                remote_path,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'
                }
            )
            
            # Get object metadata
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=remote_path
            )
            
            return {
                "success": True,
                "path": f"s3://{self.bucket_name}/{remote_path}",
                "size": response['ContentLength'],
                "etag": response['ETag'].strip('"'),
                "timestamp": datetime.now().isoformat(),
                "version_id": response.get('VersionId')
            }
        
        except self.ClientError as e:
            logger.error(f"Failed to upload to S3: {e}")
            return {"success": False, "error": str(e)}
    
    def download(self, remote_path: str, local_path: Path) -> bool:
        """Download file from S3"""
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.s3_client.download_file(
                self.bucket_name,
                remote_path,
                str(local_path)
            )
            
            return True
        
        except self.ClientError as e:
            logger.error(f"Failed to download from S3: {e}")
            return False
    
    def exists(self, remote_path: str) -> bool:
        """Check if object exists in S3"""
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=remote_path
            )
            return True
        
        except self.ClientError:
            return False
    
    def get_signed_url(self, remote_path: str, expiry_hours: int = 24) -> str:
        """Generate presigned URL for S3 object"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': remote_path
                },
                ExpiresIn=expiry_hours * 3600
            )
            return url
        
        except self.ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return ""
    
    def delete(self, remote_path: str) -> bool:
        """Delete object from S3 (if not protected)"""
        try:
            # Check for object lock
            try:
                response = self.s3_client.get_object_retention(
                    Bucket=self.bucket_name,
                    Key=remote_path
                )
                if 'Retention' in response:
                    logger.warning(f"Cannot delete object with retention: {remote_path}")
                    return False
            except self.ClientError:
                pass  # No retention set
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=remote_path
            )
            
            return True
        
        except self.ClientError as e:
            logger.error(f"Failed to delete from S3: {e}")
            return False
    
    def set_worm(self, remote_path: str, retention_days: int) -> bool:
        """Set S3 Object Lock for WORM compliance"""
        try:
            retention_date = datetime.now() + timedelta(days=retention_days)
            
            self.s3_client.put_object_retention(
                Bucket=self.bucket_name,
                Key=remote_path,
                Retention={
                    'Mode': 'COMPLIANCE',
                    'RetainUntilDate': retention_date
                }
            )
            
            logger.info(f"S3 Object Lock set for {remote_path} until {retention_date}")
            return True
        
        except self.ClientError as e:
            logger.error(f"Failed to set S3 Object Lock: {e}")
            return False


class GCSStorageAdapter(StorageAdapter):
    """Google Cloud Storage adapter"""
    
    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        """Initialize GCS storage adapter"""
        try:
            from google.cloud import storage
            from google.cloud.exceptions import NotFound
            
            self.bucket_name = bucket_name
            
            # Initialize GCS client
            if credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            self.client = storage.Client(project=project_id)
            self.bucket = self.client.bucket(bucket_name)
            self.NotFound = NotFound
            
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS. "
                "Install with: pip install google-cloud-storage"
            )
    
    def upload(self, file_path: Path, remote_path: str) -> Dict[str, Any]:
        """Upload file to GCS"""
        try:
            blob = self.bucket.blob(remote_path)
            
            # Upload with encryption
            blob.upload_from_filename(
                str(file_path),
                content_type='application/octet-stream'
            )
            
            # Set storage class for cost optimization
            blob.update_storage_class('NEARLINE')
            
            return {
                "success": True,
                "path": f"gs://{self.bucket_name}/{remote_path}",
                "size": blob.size,
                "etag": blob.etag,
                "timestamp": datetime.now().isoformat(),
                "generation": blob.generation
            }
        
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            return {"success": False, "error": str(e)}
    
    def download(self, remote_path: str, local_path: Path) -> bool:
        """Download file from GCS"""
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            blob = self.bucket.blob(remote_path)
            blob.download_to_filename(str(local_path))
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}")
            return False
    
    def exists(self, remote_path: str) -> bool:
        """Check if blob exists in GCS"""
        blob = self.bucket.blob(remote_path)
        return blob.exists()
    
    def get_signed_url(self, remote_path: str, expiry_hours: int = 24) -> str:
        """Generate signed URL for GCS object"""
        try:
            from google.cloud.storage import signing
            
            blob = self.bucket.blob(remote_path)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=expiry_hours),
                method="GET"
            )
            
            return url
        
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            return ""
    
    def delete(self, remote_path: str) -> bool:
        """Delete blob from GCS (if not protected)"""
        try:
            blob = self.bucket.blob(remote_path)
            
            # Check retention policy
            if blob.retention_expiration_time:
                if datetime.now() < blob.retention_expiration_time:
                    logger.warning(f"Cannot delete blob with retention: {remote_path}")
                    return False
            
            blob.delete()
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete from GCS: {e}")
            return False
    
    def set_worm(self, remote_path: str, retention_days: int) -> bool:
        """Set retention policy for WORM compliance"""
        try:
            blob = self.bucket.blob(remote_path)
            
            # Set retention metadata
            retention_time = datetime.now() + timedelta(days=retention_days)
            blob.metadata = {
                'retention_until': retention_time.isoformat(),
                'worm_protected': 'true'
            }
            blob.patch()
            
            # Note: Bucket-level retention policies should be configured separately
            logger.info(f"GCS retention metadata set for {remote_path} until {retention_time}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set GCS retention: {e}")
            return False


class AzureStorageAdapter(StorageAdapter):
    """Azure Blob Storage adapter"""
    
    def __init__(
        self,
        container_name: str,
        account_name: str,
        account_key: Optional[str] = None,
        connection_string: Optional[str] = None
    ):
        """Initialize Azure storage adapter"""
        try:
            from azure.storage.blob import BlobServiceClient, BlobClient
            from azure.core.exceptions import ResourceNotFoundError
            
            self.container_name = container_name
            
            # Initialize Azure client
            if connection_string:
                self.service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )
            elif account_key:
                connection_string = (
                    f"DefaultEndpointsProtocol=https;"
                    f"AccountName={account_name};"
                    f"AccountKey={account_key};"
                    f"EndpointSuffix=core.windows.net"
                )
                self.service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )
            else:
                raise ValueError("Either connection_string or account_key required")
            
            self.container_client = self.service_client.get_container_client(
                container_name
            )
            self.ResourceNotFoundError = ResourceNotFoundError
            
        except ImportError:
            raise ImportError(
                "azure-storage-blob is required for Azure. "
                "Install with: pip install azure-storage-blob"
            )
    
    def upload(self, file_path: Path, remote_path: str) -> Dict[str, Any]:
        """Upload file to Azure Blob Storage"""
        try:
            blob_client = self.container_client.get_blob_client(remote_path)
            
            with open(file_path, 'rb') as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    metadata={'uploaded_at': datetime.now().isoformat()}
                )
            
            properties = blob_client.get_blob_properties()
            
            return {
                "success": True,
                "path": f"azure://{self.container_name}/{remote_path}",
                "size": properties.size,
                "etag": properties.etag,
                "timestamp": datetime.now().isoformat(),
                "version_id": properties.version_id
            }
        
        except Exception as e:
            logger.error(f"Failed to upload to Azure: {e}")
            return {"success": False, "error": str(e)}
    
    def download(self, remote_path: str, local_path: Path) -> bool:
        """Download file from Azure Blob Storage"""
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            blob_client = self.container_client.get_blob_client(remote_path)
            
            with open(local_path, 'wb') as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to download from Azure: {e}")
            return False
    
    def exists(self, remote_path: str) -> bool:
        """Check if blob exists in Azure"""
        try:
            blob_client = self.container_client.get_blob_client(remote_path)
            blob_client.get_blob_properties()
            return True
        
        except self.ResourceNotFoundError:
            return False
    
    def get_signed_url(self, remote_path: str, expiry_hours: int = 24) -> str:
        """Generate SAS URL for Azure blob"""
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            sas_token = generate_blob_sas(
                account_name=self.service_client.account_name,
                container_name=self.container_name,
                blob_name=remote_path,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            url = (
                f"https://{self.service_client.account_name}.blob.core.windows.net/"
                f"{self.container_name}/{remote_path}?{sas_token}"
            )
            
            return url
        
        except Exception as e:
            logger.error(f"Failed to generate SAS URL: {e}")
            return ""
    
    def delete(self, remote_path: str) -> bool:
        """Delete blob from Azure (if not protected)"""
        try:
            blob_client = self.container_client.get_blob_client(remote_path)
            
            # Check immutability policy
            properties = blob_client.get_blob_properties()
            if properties.immutability_policy:
                logger.warning(f"Cannot delete immutable blob: {remote_path}")
                return False
            
            blob_client.delete_blob()
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete from Azure: {e}")
            return False
    
    def set_worm(self, remote_path: str, retention_days: int) -> bool:
        """Set immutability policy for WORM compliance"""
        try:
            from azure.storage.blob import ImmutabilityPolicy
            
            blob_client = self.container_client.get_blob_client(remote_path)
            
            retention_time = datetime.utcnow() + timedelta(days=retention_days)
            
            blob_client.set_immutability_policy(
                ImmutabilityPolicy(
                    expiry_time=retention_time,
                    policy_mode="Locked"
                )
            )
            
            logger.info(f"Azure immutability set for {remote_path} until {retention_time}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set Azure immutability: {e}")
            return False


class StorageFactory:
    """Factory for creating storage adapters"""
    
    @staticmethod
    def create_adapter(storage_type: str, config: Dict[str, Any]) -> StorageAdapter:
        """Create storage adapter based on type"""
        
        if storage_type == "local":
            return LocalStorageAdapter(
                base_path=config.get("base_path", "./audit_storage")
            )
        
        elif storage_type == "s3":
            return S3StorageAdapter(
                bucket_name=config["bucket_name"],
                region=config.get("region", "us-east-1"),
                aws_access_key_id=config.get("aws_access_key_id"),
                aws_secret_access_key=config.get("aws_secret_access_key")
            )
        
        elif storage_type == "gcs":
            return GCSStorageAdapter(
                bucket_name=config["bucket_name"],
                project_id=config.get("project_id"),
                credentials_path=config.get("credentials_path")
            )
        
        elif storage_type == "azure":
            return AzureStorageAdapter(
                container_name=config["container_name"],
                account_name=config.get("account_name"),
                account_key=config.get("account_key"),
                connection_string=config.get("connection_string")
            )
        
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
