import argparse
import json
import os
from datetime import datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from telegram_notifier import send_telegram_notification, send_status_notification

COMPANIES_FILE = "companies.json"
SEEN_JOBS_FILE = "seen_jobs.json"

SMART_EXTRACTOR_JS = """
() => {
    const results = [];
    const links = document.querySelectorAll('a[href]');

    const getMatch = (text) => {
        if (!text) return null;
        const m = text.match(/\\b(intern|interns|internship|internships|trainee|trainees)\\b/i);
        return m ? m[0].toLowerCase() : null;
    };

    const isActionWord = (text) => {
        if (!text) return true;
        const clean = text.trim().toLowerCase();
        return ['apply', 'apply now', 'view details', 'interested', 'learn more', 'details', 'view job', 'read more', 'click here', 'apply here'].includes(clean);
    };

    links.forEach(a => {
        let href = a.href;
        if (!href || href.startsWith('javascript:') || href.includes('mailto:')) return;

        let isTarget = false;
        let matchReason = "";
        let linkText = (a.innerText || '').trim();
        let ariaLabel = (a.getAttribute('aria-label') || '').trim();
        let combinedCheckText = (linkText + ' ' + ariaLabel).trim();

        // 1. Direct match on link text or aria-label
        let directMatch = getMatch(combinedCheckText);
        if (directMatch) {
            isTarget = true;
            matchReason = `Direct match on word '${directMatch}'`;
        } else {
            // 2. Parent container search (up to 6 levels)
            let parent = a.parentElement;
            let depth = 0;
            
            while (!isTarget && parent && depth < 6) {
                let parentText = parent.innerText || '';
                
                if (parentText.length > 1200) break; 
                if (parent.querySelectorAll('a[href]').length > 8) break; 
                
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
            let title = linkText;

            if (ariaLabel.toLowerCase().includes('apply for')) {
                title = ariaLabel.replace(/apply for/i, '').trim();
            } else if (isActionWord(title) || !title) {
                // Find nearest card/item container
                let container = a.closest('div[class*="card"], div[class*="border"], div[class*="job"], div[class*="vacancy"], div[class*="col"], li, tr, article') || a.parentElement?.parentElement;
                let header = container?.querySelector('h1, h2, h3, h4, h5, h6, strong, [class*="title"], [class*="heading"]');
                if (header && header.innerText.trim()) {
                    title = header.innerText.trim();
                } else if (linkText && !isActionWord(linkText)) {
                    title = linkText;
                } else {
                    title = "Intern Role (Apply Link)";
                }
            }

            // Clean up multi-line titles
            title = title.split('\\n').map(s => s.trim()).filter(Boolean).join(' - ');

            results.push({ title: title, url: href, reason: matchReason });
        }
    });
    return results;
}
"""

def load_json(filename, default_value):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading '{filename}': {e}. Using default.")
    return default_value

def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"💾 Saved updated state to '{filename}'.")

def extract_jobs_from_site(careers_url, company_name):
    found_jobs = []
    
    with sync_playwright() as p:
        print(f"\n🔍 Scraping [{company_name}] ({careers_url})...")
        
        # Launch browser with stealth settings to bypass Cloudflare bot protection
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox'
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = context.new_page()

        try:
            page.goto(careers_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500) # Give extra time for dynamic SPA content / accordions
            
            raw_results = page.evaluate(SMART_EXTRACTOR_JS)
            print(f"   Found {len(raw_results)} potential matches.")

            seen_urls_in_page = set()
            for item in raw_results:
                full_url = item['url']
                if full_url.startswith('/'):
                    parsed_uri = urlparse(careers_url)
                    base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                    full_url = base_url + full_url

                # Filter out pure tab/anchor links that are not job links (e.g. #jobs-tab-1)
                if '#' in full_url and not any(k in full_url.lower() for k in ['apply', 'job', 'careers', 'role', 'vacancy', 'id=']):
                    continue

                if full_url not in seen_urls_in_page:
                    seen_urls_in_page.add(full_url)
                    found_jobs.append({
                        "company": company_name,
                        "title": item['title'],
                        "url": full_url,
                        "reason": item.get('reason', 'Unknown'),
                        "first_seen": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            print(f"❌ Error scraping {company_name}: {e}")

        browser.close()

    return found_jobs

def run_scraper(notify_telegram: bool = True):
    companies = load_json(COMPANIES_FILE, [])
    if not companies:
        print(f"⚠️ No companies found in '{COMPANIES_FILE}'. Please add target companies first.")
        return

    seen_jobs = load_json(SEEN_JOBS_FILE, [])
    seen_urls = {job['url'] for job in seen_jobs if isinstance(job, dict) and 'url' in job}

    new_jobs_count = 0
    
    for company in companies:
        name = company.get('company_name', 'Unknown')
        url = company.get('careers_url', '')

        if not url:
            continue

        scraped_jobs = extract_jobs_from_site(url, name)
        
        for job in scraped_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                seen_jobs.append(job)
                new_jobs_count += 1
                
                print(f"✨ NEW JOB FOUND: [{job['company']}] {job['title']}")
                print(f"   URL: {job['url']}")
                
                if notify_telegram:
                    send_telegram_notification(job)
                else:
                    print("   ℹ️ Telegram notification skipped (baseline seed mode).")

    if new_jobs_count > 0:
        save_json(seen_jobs, SEEN_JOBS_FILE)
        print(f"\n✅ Total new jobs added to '{SEEN_JOBS_FILE}': {new_jobs_count}")
    else:
        print("\nℹ️ No new jobs found. State is up to date.")
        if notify_telegram:
            send_status_notification(len(companies))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scout Job Scraper")
    parser.add_argument("--seed", action="store_true", help="Run in seed mode to populate seen_jobs.json without sending Telegram alerts")
    parser.add_argument("--no-notify", action="store_true", help="Disable Telegram notifications")
    args = parser.parse_args()

    should_notify = not (args.seed or args.no_notify)
    
    if args.seed:
        print("🌱 Running in BASELINE SEED MODE. Telegram alerts are DISABLED.")
    
    run_scraper(notify_telegram=should_notify)