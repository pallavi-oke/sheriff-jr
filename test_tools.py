"""Quick sanity check that the tools work in isolation."""

from tools import fetch_policy_page, fetch_url, POLICY_URLS


def main():
    print("=" * 60)
    print("Test 1: fetch_policy_page('google-restricted-content') — local file")
    print("=" * 60)
    result = fetch_policy_page("google-restricted-content")
    print(result[:500])
    print(f"\n[total length: {len(result)} chars]\n")

    print("=" * 60)
    print("Test 2: fetch_policy_page('nonsense') — should error gracefully")
    print("=" * 60)
    print(fetch_policy_page("nonsense"))
    print()

    print("=" * 60)
    print("Test 3: fetch_url('https://example.com')")
    print("=" * 60)
    print(fetch_url("https://example.com")[:300])
    print()

    print("=" * 60)
    print(f"Available policies ({len(POLICY_URLS)}):")
    print("=" * 60)
    for name in sorted(POLICY_URLS):
        print(f"  - {name}")


if __name__ == "__main__":
    main()
