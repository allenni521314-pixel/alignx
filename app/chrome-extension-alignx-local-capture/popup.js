const ALIGNX_ORIGIN = "https://alignxagent.netlify.app";
const ALIGNX_TARGETS = {
  listing: { path: "/listing-diagnosis", label: "本品诊断" },
  competitor: { path: "/competitor-analysis", label: "竞品诊断" },
  asin: { path: "/asin-manager", label: "ASIN选品" },
};

function setStatus(message) {
  document.getElementById("status").textContent = message || "";
}

function marketplaceFromHost(hostname) {
  const host = hostname.toLowerCase();
  if (host.includes("amazon.co.uk")) return "UK";
  if (host.includes("amazon.de")) return "DE";
  if (host.includes("amazon.co.jp")) return "JP";
  if (host.includes("amazon.ca")) return "CA";
  if (host.includes("amazon.fr")) return "FR";
  if (host.includes("amazon.it")) return "IT";
  if (host.includes("amazon.es")) return "ES";
  if (host.includes("amazon.com.au")) return "AU";
  return "US";
}

async function captureAmazonPage() {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const pickText = (selectors) => {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      const text = clean(node?.textContent || node?.getAttribute?.("content") || "");
      if (text) return text;
    }
    return "";
  };
  const normalizePriceNumber = (value) => {
    let raw = clean(value);
    if (/,/.test(raw) && !/\.\d{2}\b/.test(raw)) {
      raw = raw.replace(/,(\d{2})\b/, ".$1");
    }
    const normalized = raw
      .replace(/,/g, "")
      .replace(/[^\d.]/g, "")
      .replace(/^\./, "")
      .replace(/\.(?=.*\.)/g, "");
    if (!normalized) return "";
    const amount = Number(normalized);
    if (!Number.isFinite(amount) || amount <= 0 || amount > 9999) return "";
    return amount.toFixed(2).replace(/\.00$/, "");
  };
  const parsePrice = (value, options = {}) => {
    const { allowNumberOnly = false, defaultSymbol = "$" } = options;
    const text = clean(value)
      .replace(/\u00a0/g, " ")
      .replace(/(\d)\s+(\d{2})(\D|$)/, "$1.$2$3")
      .replace(/(\d)\s*\.\s*(\d{2})(\D|$)/, "$1.$2$3");
    if (!text) return "";

    const badSinglePriceContext = /list price|was:|typical price|save\s+\d|coupon|monthly|payment plan|per month|delivery|shipping/i;
    const candidates = [];
    for (const match of text.matchAll(/([$€£¥₹])\s*(\d{1,4}(?:[,.]\s*\d{2})?)/g)) {
      const amount = normalizePriceNumber(match[2]);
      if (amount) candidates.push(`${match[1]}${amount}`);
    }
    for (const match of text.matchAll(/\b(\d{1,4}(?:[,.]\s*\d{2})?)\s*(USD|EUR|GBP|JPY|CAD|AUD)\b/gi)) {
      const amount = normalizePriceNumber(match[1]);
      if (amount) candidates.push(`${amount} ${match[2].toUpperCase()}`);
    }
    if (allowNumberOnly && candidates.length === 0) {
      const match = text.match(/\b\d{1,4}(?:[,.]\s*\d{2})?\b/);
      const amount = normalizePriceNumber(match?.[0] || "");
      if (amount) candidates.push(`${defaultSymbol}${amount}`);
    }
    if (candidates.length === 0) return "";
    if (candidates.length === 1 && badSinglePriceContext.test(text)) return "";
    return candidates[candidates.length - 1];
  };
  const pickPriceFromText = (text) => {
    const lines = String(text || "")
      .split(/\n+/)
      .map(clean)
      .filter(Boolean);
    const badLine = /list price|was:|typical price|coupon|save\s+\d|delivery|shipping|prime|monthly|payment plan|per month|price history/i;
    const goodLine = /price to pay|limited time deal|deal price|buy new|new from|amazon/i;
    const candidates = [];
    for (const line of lines.slice(0, 220)) {
      if (!/[$€£¥₹]\s*\d{1,4}/.test(line)) continue;
      const price = parsePrice(line);
      if (!price) continue;
      const score = (goodLine.test(line) ? 2 : 0) - (badLine.test(line) ? 1 : 0);
      candidates.push({ price, score, line });
    }
    candidates.sort((a, b) => b.score - a.score);
    return candidates[0]?.price || "";
  };
  const readNodePrice = (node, options = {}) => {
    if (!node) return "";
    return (
      parsePrice(node.getAttribute?.("content") || "", { ...options, allowNumberOnly: true }) ||
      parsePrice(node.getAttribute?.("value") || "", { ...options, allowNumberOnly: true }) ||
      parsePrice(node.getAttribute?.("data-price") || "", { ...options, allowNumberOnly: true }) ||
      parsePrice(node.getAttribute?.("aria-label") || "", options) ||
      parsePrice(node.textContent || "", options)
    );
  };
  const priceFromParts = (node) => {
    const symbol = clean(node.querySelector(".a-price-symbol")?.textContent || "$") || "$";
    const whole = clean(node.querySelector(".a-price-whole")?.textContent || "").replace(/[^\d]/g, "");
    const fraction = clean(node.querySelector(".a-price-fraction")?.textContent || "").replace(/[^\d]/g, "").slice(0, 2);
    if (!whole) return "";
    return parsePrice(`${symbol}${whole}${fraction ? `.${fraction}` : ""}`, { allowNumberOnly: true, defaultSymbol: symbol });
  };
  const pickPrice = () => {
    const metadataSelectors = [
      "meta[itemprop='price']",
      "meta[property='product:price:amount']",
      "input#attach-base-product-price",
      "input#twister-plus-price-data-price",
      "#twister-plus-price-data-price",
      "#sns-base-price",
      "[data-price]",
    ];
    for (const selector of metadataSelectors) {
      const price = readNodePrice(document.querySelector(selector), { allowNumberOnly: true });
      if (price) return price;
    }
    const selectors = [
      "#corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen",
      "#corePrice_feature_div .priceToPay .a-offscreen",
      "#corePriceDisplay_desktop_feature_div .apexPriceToPay .a-offscreen",
      "#corePrice_feature_div .apexPriceToPay .a-offscreen",
      "#corePriceDisplay_desktop_feature_div [data-a-color='price'] .a-offscreen",
      "#corePrice_feature_div [data-a-color='price'] .a-offscreen",
      "#corePriceDisplay_desktop_feature_div .reinventPricePriceToPayMargin .a-offscreen",
      "#corePrice_feature_div .reinventPricePriceToPayMargin .a-offscreen",
      "#corePriceDisplay_desktop_feature_div .a-price[data-a-color='price'] .a-offscreen",
      "#corePrice_feature_div .a-price[data-a-color='price'] .a-offscreen",
      "#corePriceDisplay_desktop_feature_div .a-price [aria-hidden='true']",
      "#corePrice_feature_div .a-price [aria-hidden='true']",
      "#corePrice_desktop .a-price .a-offscreen",
      "#corePrice_desktop .a-price [aria-hidden='true']",
      "#apex_desktop .a-price .a-offscreen",
      "#centerCol .a-price .a-offscreen",
      "#buybox .a-price .a-offscreen",
      "#desktop_buybox .a-price .a-offscreen",
      "#ppd .a-price .a-offscreen",
      "#newBuyBoxPrice",
      "#priceblock_ourprice",
      "#priceblock_dealprice",
      "#priceblock_saleprice",
      "#price_inside_buybox",
      ".priceToPay .a-offscreen",
      ".apexPriceToPay .a-offscreen",
    ];
    for (const selector of selectors) {
      const price = readNodePrice(document.querySelector(selector));
      if (price) return price;
    }
    for (const blockSelector of ["#corePriceDisplay_desktop_feature_div", "#corePrice_feature_div", "#corePrice_desktop", "#apex_desktop", "#buybox", "#desktop_buybox", "#centerCol", "#ppd"]) {
      const block = document.querySelector(blockSelector);
      if (!block) continue;
      const blockDirect = parsePrice(block.textContent || "");
      if (blockDirect) return blockDirect;
      for (const node of block.querySelectorAll(".a-price")) {
        const offscreen = readNodePrice(node.querySelector(".a-offscreen"));
        if (offscreen) return offscreen;
        const fromParts = priceFromParts(node);
        if (fromParts) return fromParts;
      }
    }
    return pickPriceFromText(document.body?.innerText || "");
  };
  const pickBullets = () => {
    const selectors = [
      "#feature-bullets li span.a-list-item",
      "#feature-bullets li",
      "#featurebullets_feature_div li span",
      "#featurebullets_feature_div li",
      "#feature-bullets-btf li span",
      "[id*='featurebullets'] li span",
      "[id*='featurebullets'] li",
      "#productFactsDesktop_feature_div li",
      "#productFacts_feature_div li",
      "#productFactsDesktop_feature_div .a-fixed-left-grid-col.a-col-right",
      "#productFacts_feature_div .a-fixed-left-grid-col.a-col-right",
      "[data-feature-name='featurebullets'] li span",
    ];
    const seen = new Set();
    const bullets = [];
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        const text = clean(node.textContent)
          .replace(/^[-•\s]+/, "")
          .replace(/^About this item\s*/i, "");
        if (
          text.length > 8 &&
          text.length < 700 &&
          !/see more|show more|make sure this fits|customer reviews|product information/i.test(text) &&
          !seen.has(text)
        ) {
          seen.add(text);
          bullets.push(text);
        }
        if (bullets.length >= 8) return bullets;
      }
    }
    const lines = String(document.body?.innerText || "")
      .split(/\n+/)
      .map(clean)
      .filter(Boolean);
    let inAbout = false;
    for (const line of lines) {
      if (/^about this item$/i.test(line)) {
        inAbout = true;
        continue;
      }
      if (inAbout && /^(product information|from the manufacturer|customer reviews|compare with similar items|videos)$/i.test(line)) {
        break;
      }
      if (!inAbout) continue;
      const text = line.replace(/^[-•\s]+/, "");
      if (
        text.length > 20 &&
        text.length < 700 &&
        !/see more|show more|make sure this fits|customer reviews|product information/i.test(text) &&
        !seen.has(text)
      ) {
        seen.add(text);
        bullets.push(text);
      }
      if (bullets.length >= 8) return bullets;
    }
    return bullets;
  };
  const revealAmazonDetails = async () => {
    const originalY = window.scrollY;
    const detailSelectors = [
      "#detailBulletsWrapper_feature_div",
      "#detailBullets_feature_div",
      "#productDetails_detailBullets_sections1",
      "#productDetails_db_sections",
      "#productDetails_techSpec_section_1",
      "#prodDetails",
      "#productDetails_feature_div",
    ];

    const expanders = Array.from(document.querySelectorAll("a, button"))
      .filter((node) => /show more|see more product details|show product details|product details/i.test(clean(node.textContent || node.getAttribute("aria-label") || "")))
      .slice(0, 4);
    for (const node of expanders) {
      try {
        node.click();
        await wait(180);
      } catch (_) {
        // Best effort only: Amazon variants do not expose a stable expander API.
      }
    }

    let foundDetails = false;
    for (const selector of detailSelectors) {
      const node = document.querySelector(selector);
      if (!node) continue;
      foundDetails = true;
      try {
        node.scrollIntoView({ block: "center", behavior: "auto" });
      } catch (_) {
        node.scrollIntoView({ block: "center" });
      }
      await wait(260);
    }

    if (!foundDetails) {
      const height = Math.max(document.documentElement.scrollHeight || 0, document.body?.scrollHeight || 0);
      for (const ratio of [0.35, 0.55, 0.75, 0.9]) {
        window.scrollTo(0, Math.round(height * ratio));
        await wait(220);
      }
    }

    window.scrollTo(0, originalY);
    await wait(80);
  };
  const normalizeBsrText = (value) => {
    let text = clean(value)
      .replace(/\u200e|\u200f/g, "")
      .replace(/Best Sellers Rank\s*[:：]?/i, "")
      .replace(/Amazon Best Sellers Rank\s*[:：]?/i, "")
      .trim();
    if (!text) return "";
    const direct = text.match(/#\s*[\d,.\s]+(?:\s+in\s+[^#|]+)?/i);
    if (direct) text = direct[0];
    text = clean(text)
      .replace(/\s*\(?\s*See Top 100[^\)]*\)?/i, "")
      .replace(/\s*\(?\s*Top 100[^\)]*\)?/i, "")
      .replace(/\s+#[\d,.\s]+\s+in\s+/g, " | #")
      .replace(/\s{2,}/g, " ")
      .trim();
    return text.slice(0, 220);
  };
  const pickBsrRank = () => {
    const bsrLabelPattern = /best\s*sellers?\s*rank|sales\s*rank|amazon\s*best\s*sellers?\s*rank|畅销|销售排名|ランキング/i;
    const detailSelectors = [
      "#productDetails_detailBullets_sections1",
      "#productDetails_db_sections",
      "#productDetails_techSpec_section_1",
      "#prodDetails",
      "#detailBulletsWrapper_feature_div",
      "#detailBullets_feature_div",
      "#productDetails_feature_div",
      "[id*='SalesRank']",
      "[id*='salesRank']",
    ];

    for (const selector of ["#productDetails_detailBullets_sections1 tr", "#productDetails_db_sections tr", "#productDetails_techSpec_section_1 tr", "#prodDetails tr"]) {
      for (const row of document.querySelectorAll(selector)) {
        const header = clean(row.querySelector("th, .a-text-bold")?.textContent || "");
        const value = clean(row.querySelector("td")?.textContent || row.textContent || "");
        if (bsrLabelPattern.test(header) || bsrLabelPattern.test(value)) {
          const parsed = normalizeBsrText(value);
          if (parsed) return parsed;
        }
      }
    }

    for (const selector of detailSelectors) {
      const node = document.querySelector(selector);
      if (!node) continue;
      const text = clean(node.textContent || "");
      if (bsrLabelPattern.test(text)) {
        const labelMatch = text.match(/(?:Amazon\s*)?Best\s*Sellers?\s*Rank\s*[:：]?\s*(#[\d,.\s]+(?:\s+in\s+.{2,180})?)/i);
        const parsed = normalizeBsrText(labelMatch?.[1] || text);
        if (parsed) return parsed;
      }
      const direct = text.match(/#\s*[\d,.\s]+\s+in\s+[^#|]{3,180}/i);
      const parsed = normalizeBsrText(direct?.[0] || "");
      if (parsed) return parsed;
    }

    const bodyText = String(document.body?.innerText || "");
    const multiline = bodyText.match(/(?:Amazon\s*)?Best\s*Sellers?\s*Rank\s*[:：]?\s*([\s\S]{0,320}?)(?=\n\s*(?:Customer Reviews|Product Dimensions|Date First Available|ASIN|Manufacturer|Item model number|Best Sellers Rank|$))/i);
    const parsedFromLabel = normalizeBsrText(multiline?.[1] || "");
    if (parsedFromLabel) return parsedFromLabel;

    const direct = bodyText.match(/#\s*[\d,.\s]+\s+in\s+[^\n\r]{3,180}/i);
    return normalizeBsrText(direct?.[0] || "");
  };
  const marketplaceFromCurrentHost = (hostname) => {
    const host = String(hostname || "").toLowerCase();
    if (host.includes("amazon.co.uk")) return "UK";
    if (host.includes("amazon.de")) return "DE";
    if (host.includes("amazon.co.jp")) return "JP";
    if (host.includes("amazon.ca")) return "CA";
    if (host.includes("amazon.fr")) return "FR";
    if (host.includes("amazon.it")) return "IT";
    if (host.includes("amazon.es")) return "ES";
    if (host.includes("amazon.com.au")) return "AU";
    return "US";
  };
  await revealAmazonDetails();
  const url = location.href;
  const safeText = clean(document.body?.innerText || "");
  const asinMatch =
    url.match(/\/(?:dp|gp\/product|product)\/([A-Z0-9]{10})/i) ||
    url.match(/[?&]asin=([A-Z0-9]{10})/i) ||
    safeText.match(/\bB0[A-Z0-9]{8}\b/);
  const urlTitle = decodeURIComponent(url.split("/dp/")[0].split("/").pop() || "").replace(/-/g, " ");
  const title = clean(
    document.querySelector("#productTitle")?.textContent ||
      document.querySelector("[data-automation-id='product-title']")?.textContent ||
      document.querySelector("meta[property='og:title']")?.getAttribute("content") ||
      document.querySelector("meta[name='title']")?.getAttribute("content") ||
      document.querySelector("h1")?.textContent ||
      document.title ||
      urlTitle
  );
  const bullets = pickBullets();
  const price = pickPrice();
  const rating = pickText(["#acrPopover span.a-icon-alt", "#averageCustomerReviews span.a-icon-alt", "span[data-hook='rating-out-of-text']"]);
  const reviewCount = pickText(["#acrCustomerReviewText", "[data-hook='total-review-count']"]);
  const bsrRank = pickBsrRank();
  const images = Array.from(document.querySelectorAll("#altImages img, img"))
    .map((img) => img.currentSrc || img.src || "")
    .filter(Boolean)
    .slice(0, 20);
  const clone = document.documentElement.cloneNode(true);
  clone.querySelectorAll("script, style, noscript, iframe, svg").forEach((node) => node.remove());
  const html = `<!doctype html>\n${clone.outerHTML}`;

  return {
    source: "local_browser_capture",
    capturedAt: new Date().toISOString(),
    url,
    hostname: location.hostname,
    marketplace: marketplaceFromCurrentHost(location.hostname),
    asin: asinMatch ? String(asinMatch[1] || asinMatch[0]).toUpperCase() : "",
    title,
    price,
    rating,
    reviewCount,
    bsrRank,
    bullets,
    imageCount: images.length,
    html,
    text: safeText.slice(0, 20000),
    debug: {
      hasBody: Boolean(document.body),
      titleLength: title.length,
      textLength: safeText.length,
      htmlLength: html.length,
      productTitleFound: Boolean(document.querySelector("#productTitle")),
      h1Found: Boolean(document.querySelector("h1")),
      bsrDetailsFound: Boolean(document.querySelector("#detailBulletsWrapper_feature_div, #detailBullets_feature_div, #productDetails_detailBullets_sections1, #productDetails_db_sections, #prodDetails, [id*='SalesRank'], [id*='salesRank']")),
      bsrRankFound: Boolean(bsrRank),
    },
  };
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function renderCapture(capture) {
  const result = document.getElementById("result");
  result.hidden = false;
  result.replaceChildren();
  [
    ["ASIN", capture.asin || "未识别"],
    ["站点", capture.marketplace || "未识别"],
    ["标题", capture.title || "未识别"],
    ["价格", capture.price || "未识别"],
    ["评分", capture.rating || "未识别"],
    ["评论数", capture.reviewCount || "未识别"],
    ["BSR", capture.bsrRank || "未识别"],
    ["五点", String(capture.bullets?.length || 0)],
    ["图片", String(capture.imageCount || 0)],
    ["HTML", `${Math.round((capture.html?.length || 0) / 1024)} KB`],
    ["文本", `${Math.round((capture.text?.length || 0) / 1024)} KB`],
  ].forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "row";
    const key = document.createElement("span");
    key.className = "key";
    key.textContent = label;
    const val = document.createElement("span");
    val.className = "val";
    val.textContent = value;
    row.append(key, val);
    result.append(row);
  });
}

async function captureCurrentPage() {
  setStatus("正在读取当前页面...");
  const tab = await getActiveTab();
  if (!tab?.url || !/amazon\./i.test(tab.url)) {
    setStatus("请先切换到 Amazon 商品详情页，再点击采集。");
    return;
  }

  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: captureAmazonPage,
  });
  const capture = result?.result;
  if (!capture?.html || (!capture?.asin && !/\/(?:dp|gp\/product|product)\//i.test(capture?.url || ""))) {
    const debug = capture?.debug ? ` 调试：${JSON.stringify(capture.debug)}` : "";
    setStatus(`未读取到有效商品页内容，请确认当前页面是 Amazon 商品详情页。${debug}`);
    return;
  }

  await chrome.storage.local.set({ alignxLastCapture: capture });
  renderCapture(capture);
  setStatus("已采集到本地页面。请选择分析模块后点击“发送并开始分析”。AlignX会显示分析过程，不会静默写入历史。");
}

async function openAlignX() {
  const { alignxLastCapture } = await chrome.storage.local.get("alignxLastCapture");
  if (!alignxLastCapture) {
    setStatus("还没有采集结果，请先在 Amazon 商品页点击采集。");
    return;
  }

  const targetKey = document.getElementById("target")?.value || "listing";
  const target = ALIGNX_TARGETS[targetKey] || ALIGNX_TARGETS.listing;
  const capture = { ...alignxLastCapture, destination: targetKey };
  const url = `${ALIGNX_ORIGIN}${target.path}?localCapture=1&asin=${encodeURIComponent(capture.asin || "")}`;
  await chrome.storage.local.set({ alignxPendingCapture: capture });
  const tabs = await chrome.tabs.query({ url: `${ALIGNX_ORIGIN}/*` });
  if (tabs[0]?.id) {
    await chrome.tabs.update(tabs[0].id, { url, active: true });
    if (tabs[0].windowId) await chrome.windows.update(tabs[0].windowId, { focused: true });
  } else {
    await chrome.tabs.create({ url });
  }
  setStatus(`正在进入 AlignX ${target.label}并开始分析；会复用已有 AlignX 标签页。`);
}

document.getElementById("capture").addEventListener("click", () => {
  captureCurrentPage().catch((error) => setStatus(error?.message || "采集失败"));
});

document.getElementById("open").addEventListener("click", () => {
  openAlignX().catch((error) => setStatus(error?.message || "打开失败"));
});
