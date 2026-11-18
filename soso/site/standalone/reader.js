(function () {
  "use strict";
  var bundle = JSON.parse(document.getElementById("bundle-data").textContent);
  var channel = "science-olympiad-standalone-v1", urls = {}, frames = {}, current = "", fragment = "";
  var status = document.getElementById("reader-status"), region = document.getElementById("pages");
  var step = 0, maximum = 0;
  function displayTitle(title) {
    var event = /^(\d{4}) (.+)$/.exec(bundle.title);
    return event ? title.replace(bundle.title, event[2]).replace(event[2] + " " + event[1], event[2]) : title;
  }
  function tokens(text) {
    return text.replace(/__SO_ASSET_([a-f0-9]{64})__/g, function (_, id) {
      if (!urls[id]) throw new Error("Missing embedded resource " + id);
      return urls[id];
    });
  }
  function bytes(value) {
    var decoded = atob(value), result = new Uint8Array(decoded.length);
    for (var i = 0; i < decoded.length; i++) result[i] = decoded.charCodeAt(i);
    return result;
  }
  Object.keys(bundle.assets).forEach(function (id) {
    var item = bundle.assets[id];
    if (item.base64) urls[id] = URL.createObjectURL(new Blob([bytes(item.base64)], { type: item.mime }));
  });
  Object.keys(bundle.assets).forEach(function (id) {
    var item = bundle.assets[id];
    if (typeof item.text === "string") urls[id] = URL.createObjectURL(new Blob([tokens(item.text)], { type: item.mime + ";charset=utf-8" }));
  });
  function hashFor(page, anchor) {
    return "#page=" + encodeURIComponent(page) + "&anchor=" + encodeURIComponent(anchor || "");
  }
  function scroll(record) {
    if (record.loaded) record.frame.contentWindow.postMessage({ channel: channel, type: "scroll", fragment: fragment }, "*");
  }
  function show() {
    var params = new URLSearchParams(location.hash.slice(1)), page = params.get("page") || bundle.entry;
    if (!Object.prototype.hasOwnProperty.call(bundle.pages, page)) page = bundle.entry;
    fragment = params.get("anchor") || "";
    var previous = history.state;
    if (previous && previous.soReader === bundle.title) {
      step = previous.step;
    } else {
      step += 1;
      maximum = step;
      history.replaceState({ soReader: bundle.title, step: step }, "");
    }
    current = page;
    if (!frames[page]) {
      var iframe = document.createElement("iframe"), record = { frame: iframe, loaded: false };
      iframe.title = bundle.pages[page].title;
      iframe.hidden = true;
      iframe.addEventListener("load", function () {
        record.loaded = true;
        iframe.setAttribute("data-ready", "true");
        if (current === page) scroll(record);
      });
      frames[page] = record;
      region.appendChild(iframe);
      iframe.srcdoc = tokens(bundle.pages[page].html);
    }
    Object.keys(frames).forEach(function (key) { frames[key].frame.hidden = key !== page; });
    scroll(frames[page]);
    document.getElementById("page-title").textContent = displayTitle(bundle.pages[page].title);
    document.getElementById("back").disabled = step <= 0;
    document.getElementById("forward").disabled = step >= maximum;
    document.body.setAttribute("data-current-page", page);
    status.textContent = "";
  }
  function navigate(page, anchor) {
    if (!Object.prototype.hasOwnProperty.call(bundle.pages, page)) return;
    var hash = hashFor(page, anchor);
    if (location.hash === hash) show();
    else {
      maximum = step + 1;
      history.pushState({ soReader: bundle.title, step: maximum }, "", hash);
      show();
    }
  }
  window.addEventListener("message", function (event) {
    if (!event.data || event.data.channel !== channel) return;
    var known = Object.keys(frames).some(function (page) { return frames[page].frame.contentWindow === event.source; });
    if (!known) return;
    if (event.data.type === "navigate") navigate(event.data.page, event.data.fragment);
    if (event.data.type === "pdf-separate") status.textContent = "Printable PDFs are supplied separately.";
  });
  window.addEventListener("hashchange", show);
  window.addEventListener("popstate", show);
  document.getElementById("home").addEventListener("click", function () { navigate(bundle.entry, ""); });
  document.getElementById("back").addEventListener("click", function () { history.back(); });
  document.getElementById("forward").addEventListener("click", function () { history.forward(); });
  document.getElementById("print").addEventListener("click", function () {
    frames[current].frame.contentWindow.focus();
    frames[current].frame.contentWindow.print();
  });
  var list = document.getElementById("pdf-list");
  bundle.pdfs.forEach(function (item) {
    var link = document.createElement("a");
    link.href = urls[item.asset]; link.target = "_blank"; link.rel = "noopener";
    link.textContent = item.name; list.appendChild(link);
  });
  document.getElementById("pdf-menu").hidden = bundle.pdfs.length === 0;
  document.body.setAttribute("data-pdfs", String(bundle.pdfs.length > 0));
  history.replaceState({ soReader: bundle.title, step: 0 }, "");
  show();
})();

