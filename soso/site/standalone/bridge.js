(function () {
  "use strict";
  var channel = "science-olympiad-standalone-v1";
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest("a");
    if (!link) return;
    if (link.hasAttribute("data-so-separate-pdf")) {
      event.preventDefault();
      parent.postMessage({ channel: channel, type: "pdf-separate" }, "*");
      return;
    }
    if (!link.hasAttribute("data-so-page")) return;
    event.preventDefault();
    var page = link.getAttribute("data-so-page"), fragment = link.getAttribute("data-so-fragment") || "";
    if (event.metaKey || event.ctrlKey || event.shiftKey) {
      var hash = "#page=" + encodeURIComponent(page) + "&anchor=" + encodeURIComponent(fragment);
      window.open(parent.location.href.split("#")[0] + hash, "_blank", "noopener");
    } else {
      parent.postMessage({ channel: channel, type: "navigate", page: page, fragment: fragment }, "*");
    }
  }, true);
  window.addEventListener("message", function (event) {
    if (event.source !== parent || !event.data || event.data.channel !== channel || event.data.type !== "scroll") return;
    var fragment = event.data.fragment;
    if (!fragment) return;
    var target = document.getElementById(fragment);
    if (!target) return;
    for (var node = target; node; node = node.parentElement) {
      if (node.tagName === "DETAILS") node.open = true;
    }
    target.scrollIntoView({ block: "start" });
  });
})();

