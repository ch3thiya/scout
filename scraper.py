import json
import os
from playwright.sync_api import sync_playwright

CAREERS_URL = "https://codimite.ai/careers/#openings-section" 
COMPANY_NAME = "SnapDrum"

def extract_jobs_from_site():
    found_jobs = []
    
    smart_extractor_js = """
    () => {
        const results = [];
        const links = document.querySelectorAll('a[href]');

        // 1. Helper function using Regex with word boundaries (\b)
        // This ensures "intern" matches but "international" or "internal" do not.
        const getMatch = (text) => {
            if (!text) return null;
            const m = text.match(/\\b(intern|interns|internship|internships|trainee|trainees)\\b/i);
            return m ? m[0].toLowerCase() : null;
        };

        links.forEach(a => {
            const href = a.href;
            if (href.startsWith('javascript:') || href.includes('mailto:')) return;

            let isTarget = false;
            let matchReason = "";
            let linkText = a.innerText;

            // 2. Check direct link text with the exact word match
            let directMatch = getMatch(linkText);
            if (directMatch) {
                isTarget = true;
                matchReason = `Direct link text matched exact word '${directMatch}'`;
            } else {
                let parent = a.parentElement;
                let depth = 0;
                
                while (!isTarget && parent && depth < 4) {
                    let parentText = parent.innerText || '';
                    
                    if (parentText.length > 800) break; 
                    if (parent.querySelectorAll('a').length > 5) break; 
                    
                    // 3. Check the parent text with the exact word match
                    let parentMatch = getMatch(parentText);
                    if (parentMatch) {
                        isTarget = true;
                        let cleanText = parentText.replace(/\\n/g, ' ').substring(0, 80);
                        matchReason = `Matched exact word '${parentMatch}' in parent (Depth ${depth + 1}): "${cleanText}..."`;
                    }
                    
                    parent = parent.parentElement;
                    depth++;
                }
            }

            if (isTarget) {
                let title = a.innerText.trim();
                if (!title || title.toLowerCase() === 'apply' || title.toLowerCase() === 'apply now' || title.toLowerCase() === 'view details') {
                    let header = a.closest('div, li, tr')?.querySelector('h1, h2, h3, h4, strong');
                    title = header ? header.innerText.trim() : "Intern Role (Apply Link)";
                }
                
                results.push({ title: title, url: href, reason: matchReason });
            }
        });
        return results;
    }
    """

    with sync_playwright() as p:
        print("Launching headless browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Navigating to {CAREERS_URL}...")
        try:
            page.goto(CAREERS_URL, wait_until="networkidle", timeout=60000)
            
            raw_results = page.evaluate(smart_extractor_js)
            print(f"Heuristic scanner found {len(raw_results)} potential matches.")

            seen_urls = set()
            for item in raw_results:
                full_url = item['url']
                if full_url.startswith('/'):
                    from urllib.parse import urlparse
                    parsed_uri = urlparse(CAREERS_URL)
                    base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    full_url = base_url + full_url

                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    found_jobs.append({
                        "company": COMPANY_NAME,
                        "title": item['title'],
                        "url": full_url,
                        "reason": item.get('reason', 'Unknown')
                    })
                    
        except Exception as e:
            print(f"Error scraping page: {e}")

        browser.close()

    return found_jobs

def save_to_json(data, filename="jobs_found.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"\nSaved {len(data)} unique job(s) to '{filename}'.")

if __name__ == "__main__":
    jobs = extract_jobs_from_site()

    print("\n--- Scrape Results ---")
    if jobs:
        for idx, job in enumerate(jobs, 1):
            print(f"[{idx}] {job['title']}")
            print(f"    Link: {job['url']}")
            print(f"    Reason: {job['reason']}\n")
    else:
        print("No matching intern positions found.")

    save_to_json(jobs)