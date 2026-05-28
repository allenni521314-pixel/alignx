async function deliverPendingCapture() {
  const { alignxPendingCapture } = await chrome.storage.local.get("alignxPendingCapture");
  if (!alignxPendingCapture?.html || !alignxPendingCapture?.asin) return;

  localStorage.setItem("alignx_local_browser_capture", JSON.stringify(alignxPendingCapture));
  window.dispatchEvent(new Event("alignx-local-browser-capture"));
  await chrome.storage.local.remove("alignxPendingCapture");
}

deliverPendingCapture().catch(() => {});
