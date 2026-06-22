from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class RedditSubredditSchema(BaseModel):
    owned: bool = False
    sorts: List[str] = Field(default_factory=list)
    track_keywords: List[str] = Field(default_factory=list)

class DomainMonitoringSchema(BaseModel):
    enabled: bool = False
    domains: List[str] = Field(default_factory=list)
    max_pages: int = Field(default=3, ge=1, le=20)
    sort: str = "relevance"

class RedditConfigSchema(BaseModel):
    subreddits: Dict[str, RedditSubredditSchema] = Field(default_factory=dict)
    domain_monitoring: Optional[DomainMonitoringSchema] = None

class DiscordServerConfigSchema(BaseModel):
    name: str
    channels: Dict[str, str] = Field(default_factory=dict)

class DiscordConfigSchema(BaseModel):
    servers: Dict[str, DiscordServerConfigSchema] = Field(default_factory=dict)

class ClientConfigSchema(BaseModel):
    name: str = Field(min_length=1)
    reddit: Optional[RedditConfigSchema] = None
    discord: Optional[DiscordConfigSchema] = None
