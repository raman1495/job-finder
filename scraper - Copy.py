import requests
import os

RAPID_API_KEY = os.getenv("RAPIDAPI_KEY")

if not RAPID_API_KEY:
    print("\n⚠ WARNING: RAPIDAPI_KEY is not set! Using placeholder.\n")


def scrape_jobs(keyword="developer", city="Toronto", postal=""):
    print(f"🧠 Fetching jobs for '{keyword}' in '{city}' via JSearch API...")

    url = "https://jsearch.p.rapidapi.com/search"
    
    query = keyword
    if city:
        query += f" in {city}"
    if postal:
        query += f" {postal}"

    params = {
        "query": query,
        "page": "1",
        "num_pages": "1"
    }

    headers = {
        "x-rapidapi-key": RAPID_API_KEY or "a0e8e576f9msh0a485a2179cc072p160876jsn7e16a90bd2fa",
        "x-rapidapi-host": "jsearch.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # raises error for bad HTTP status
        data = response.json()
    except Exception as e:
        print(f"❌ API ERROR: {e}")
        return []

    results = data.get("data", [])
    jobs = []

    for job in results:
        title = job.get("job_title")
        company = job.get("employer_name")
        loc = job.get("job_city") or job.get("job_country") or "Unknown Location"
        desc = job.get("job_description", "").strip()

        # Clean description for modal
        if desc:
            desc = desc.replace("\r", "").replace("\t", "").strip()
        else:
            desc = "No description available."

        # Truncate VERY large descriptions
        if len(desc) > 5000:
            desc = desc[:5000] + "...\n\n[Description truncated]"

        if title and company:
            jobs.append({
                "title": title,
                "company": company,
                "location": loc,
                "description": desc
            })

    print(f"✅ Found {len(jobs)} jobs")
    return jobs
