"""Chromium integration test. Run against a locally started production build."""
import os
from playwright.sync_api import sync_playwright

origin = os.environ.get("READER_TEST_ORIGIN", "http://127.0.0.1:3000")
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=[
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
    ])
    context = browser.new_context(viewport={"width": 390, "height": 844}, permissions=["microphone"])
    page = context.new_page()
    posts = []
    page.on("request", lambda req: posts.append(req.url) if req.method == "POST" else None)
    page.goto(origin + "/?surah=1&ayah=1")
    record = page.get_by_role("button", name="Record my recitation")
    record.click(timeout=30000)
    page.get_by_text("Recording…", exact=True).wait_for()
    page.wait_for_timeout(1100)
    page.get_by_role("button", name="Finish recording").click()
    audio = page.locator('audio[aria-label="Your recitation"]')
    audio.wait_for()
    assert audio.get_attribute("src").startswith("blob:")
    audio.evaluate("(a)=>a.play()")
    page.get_by_role("button", name="Discard recording").click()
    assert audio.count() == 0

    # Resolve permission after cancellation. The acquired tracks must end.
    page.evaluate("""() => {
      const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async (...args) => {
        const stream = await original(...args);
        window.testStream = stream;
        await new Promise(resolve => window.releasePermission = resolve);
        return stream;
      };
    }""")
    record.click()
    page.get_by_role("button", name="Cancel microphone request").click()
    page.wait_for_function("typeof window.releasePermission === 'function'")
    page.evaluate("window.releasePermission()")
    page.wait_for_function("window.testStream.getTracks().every(t => t.readyState === 'ended')")
    assert not posts, posts
    print("Recorded and replayed simulated microphone input, discarded it, cancelled pending capture; zero POSTs.")
    browser.close()
