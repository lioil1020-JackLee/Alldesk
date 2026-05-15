"""Domain models for Alldesk."""

from dataclasses import dataclass


@dataclass
class Client:
    tag: str = ""
    id: str = ""
    pwd: str = ""
    port: str = ""
