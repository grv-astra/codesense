import httpx
from io import BytesIO
 
async def download_github_repo_zip(token: str, username: str, repo: str, branch: str):
    url = f"https://api.github.com/repos/{username}/{repo}/zipball/{branch}"
 
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Codesense-Scanner"
    }
 
    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
 
    if response.status_code != 200:
        raise Exception(
            f"GitHub API Error ({response.status_code}): {response.text}"
        )
 
    return BytesIO(response.content)