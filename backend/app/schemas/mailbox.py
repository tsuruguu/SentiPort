from pydantic import BaseModel
from typing import List, Dict, Any


class SyncInboxRequest(BaseModel):
    """
    Dane do połączenia z konkretną skrzynką IMAP.
    Domyślne wartości pozwalają testować od razu z kontem 'agent'
    bez podawania niczego w body, jeśli backend i mailserver są
    w tej samej sieci docker-compose.
    """
    imap_host: str = "mailserver"
    imap_port: int = 143
    user: str = "agent@sentiport.pl"
    password: str = "haslo123"


class SyncInboxResponse(BaseModel):
    imported_count: int
    skipped_duplicates_count: int
    failed_count: int
    imported: List[Dict[str, Any]]
    skipped_duplicates: List[str]
    failed: List[Dict[str, Any]]