/* Channel Size Tracker: category filters, copy and share buttons, optional cookieless counts, and a self-test
   (?selftest=1) that headless Chrome runs in CI against the built and the live site. */
(function () {
  "use strict";
  var errors = [];
  window.addEventListener("error", function (e) { errors.push(String(e.message || e)); });

  function count(name) {
    try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: name, event: true }); } catch (e) { /* counting is optional */ }
  }
  function flash(btn, text) {
    var old = btn.textContent;
    btn.textContent = text;
    setTimeout(function () { btn.textContent = old; }, 1600);
  }

  // Filters on the home page: show cards whose training answer matches.
  var filterButtons = document.querySelectorAll("[data-filter]");
  Array.prototype.forEach.call(filterButtons, function (btn) {
    btn.addEventListener("click", function () {
      var want = btn.getAttribute("data-filter");
      Array.prototype.forEach.call(filterButtons, function (b) { b.setAttribute("aria-pressed", b === btn ? "true" : "false"); });
      Array.prototype.forEach.call(document.querySelectorAll("[data-cat]"), function (c) {
        c.hidden = !!want && c.getAttribute("data-cat") !== want;
      });
      count("filter/" + (want || "all"));
    });
  });

  // Copy buttons: data-copy="#id" copies that element's text.
  Array.prototype.forEach.call(document.querySelectorAll("[data-copy]"), function (btn) {
    btn.addEventListener("click", function () {
      var el = document.querySelector(btn.getAttribute("data-copy"));
      if (!el) return;
      var text = el.value || el.textContent;
      var done = function () { flash(btn, "Copied"); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { el.select && el.select(); });
      } else if (el.select) { el.select(); try { document.execCommand("copy"); done(); } catch (e) { /* ignore */ } }
      count("copy/" + btn.getAttribute("data-copy").slice(1));
    });
  });

  // Share buttons: the system share sheet where there is one, otherwise copy the link.
  Array.prototype.forEach.call(document.querySelectorAll("[data-share]"), function (btn) {
    btn.addEventListener("click", function () {
      var url = (document.querySelector('link[rel=canonical]') || {}).href || location.href;
      if (navigator.share) {
        navigator.share({ title: document.title, url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () { flash(btn, "Link copied"); });
      }
      count("share");
    });
  });

  // Activation: a visitor follows a quote to the company's own document.
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a.src");
    if (a) count("source-click");
  });

  // Self-test, used by scripts/e2e.mjs. It checks what a visitor relies on, derived from the page itself.
  if (/[?&]selftest=1/.test(location.search)) {
    window.addEventListener("load", function () {
      setTimeout(function () {
        var fails = [];
        var ok = function (cond, msg) { if (!cond) fails.push(msg); };
        ok(document.querySelector("h1"), "page has a heading");
        ok(document.querySelector('link[rel=canonical]'), "page has a canonical URL");
        Array.prototype.forEach.call(document.querySelectorAll('script[type="application/ld+json"]'), function (s, i) {
          try { JSON.parse(s.textContent); } catch (e) { fails.push("structured data block " + i + " parses"); }
        });
        if (document.querySelector(".scorebox")) {
          ok(document.querySelector(".scorebox time"), "channel page shows an as-of time");
          ok(/\d/.test(document.querySelector(".scorebox .big").textContent), "channel page shows a count");
          ok(document.querySelector("a.correction"), "channel page has a report link");
          ok(document.querySelector('a[href$=".csv"]'), "channel page links its history CSV");
          ok(document.querySelector("figure.chart svg") || document.querySelector("figure.chart, .section p.small"), "channel page has a chart or a note");
        }
        var list = document.querySelector("#list");
        if (list) {
          var n = list.querySelectorAll("tbody tr").length;
          ok(n > 0 && n === Number(list.getAttribute("data-count")), "home lists every channel");
          var first = document.querySelector("[data-filter]:not([data-filter=''])");
          if (first) {
            first.click();
            var shown = list.querySelectorAll("tbody tr:not([hidden])").length;
            ok(shown > 0 && shown <= n, "a category filter shows a subset");
            document.querySelector("[data-filter='']").click();
            ok(list.querySelectorAll("tbody tr:not([hidden])").length === n, "'All' shows every channel again");
          }
        }
        ok(errors.length === 0, "no script errors: " + errors.join("; "));
        var out = document.getElementById("selftest");
        out.hidden = false;
        out.setAttribute("data-selftest", fails.length ? "fail" : "pass");
        out.textContent = fails.length ? "FAIL\n" + fails.join("\n") : "PASS";
      }, 300);
    });
  }
})();
