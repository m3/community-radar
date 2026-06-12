def build_domain_json_url(domain: str, sort: str = "new", limit: int = 100, after: str = None) -> str:
    url = f"https://www.reddit.com/domain/{domain}/{sort}.json?limit={limit}"
    if after:
        url += f"&after={after}"
    return url
