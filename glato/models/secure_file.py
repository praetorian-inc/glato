# glato/models/secure_file.py

from dataclasses import dataclass
from typing import Optional, Dict
from datetime import datetime


@dataclass
class SecureFile:
    """Represents a GitLab secure file with its metadata"""
    id: int
    name: str
    checksum: str
    checksum_algorithm: str
    created_at: datetime
    expires_at: Optional[datetime]
    metadata: Optional[Dict]

    @staticmethod
    def from_api_response(data: Dict) -> 'SecureFile':
        """Create a SecureFile instance from API response data"""
        return SecureFile(
            id=data['id'],
            name=data['name'],
            checksum=data['checksum'],
            checksum_algorithm=data['checksum_algorithm'],
            created_at=datetime.fromisoformat(
                data['created_at'].replace(
                    'Z',
                    '+00:00')),
            expires_at=datetime.fromisoformat(
                data['expires_at'].replace(
                    'Z',
                    '+00:00')) if data.get('expires_at') else None,
            metadata=data.get('metadata'))

    @staticmethod
    def print_secure_files(secure_files, role):
        if role < 30:
            return
        if secure_files is None:
            print("Found 0 secure files.")
            return
        print(f"Found {len(secure_files)} secure file(s).")
        for sf in secure_files:
            print(f"  - {sf.name} (Created: {sf.created_at.date()})")
            if sf.metadata:
                print(
                    f"    Metadata present - check UI or send API request to /api/v4/projects/:project_id/secure_files for details")
