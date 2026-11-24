// Mirrors the anonymous device token in localStorage and IndexedDB (D37).
// Why: one phone must not check in twice by deleting its cookies. The token is random and
// signed by the server; it identifies a browser, never a person (D5, D6).
(function () {
  "use strict";
  var KEY = "dt";
  var RELOAD_FLAG = "dtReloaded";

  function readLocal() {
    try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; }
  }
  function writeLocal(token) {
    try { localStorage.setItem(KEY, token); } catch (e) { /* storage blocked: other copies remain */ }
  }
  function openDb() {
    return new Promise(function (resolve, reject) {
      var request = indexedDB.open("teaching-tool", 1);
      request.onupgradeneeded = function () { request.result.createObjectStore("kv"); };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
  }
  function readIdb() {
    return openDb().then(function (db) {
      return new Promise(function (resolve) {
        var get = db.transaction("kv").objectStore("kv").get(KEY);
        get.onsuccess = function () { resolve(get.result || ""); };
        get.onerror = function () { resolve(""); };
      });
    }).catch(function () { return ""; });
  }
  function writeIdb(token) {
    return openDb().then(function (db) {
      db.transaction("kv", "readwrite").objectStore("kv").put(token, KEY);
    }).catch(function () { /* IndexedDB unavailable (private mode): other copies remain */ });
  }
  function fillForms(token) {
    document.querySelectorAll("input[name=dt_stored]").forEach(function (input) { input.value = token; });
  }

  readIdb().then(function (idbToken) {
    var stored = [readLocal(), idbToken].filter(Boolean);
    if (stored.length) fillForms(stored[0]);  // backstop if the user submits before the sync answers
    return fetch("/device/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stored: stored }),
      cache: "no-store"
    }).then(function (response) { return response.json(); }).then(function (data) {
      if (readLocal() !== data.token) writeLocal(data.token);
      if (idbToken !== data.token) writeIdb(data.token);
      fillForms(data.token);
      // The scan window was opened under the new cookie: reload once so it is reopened under the restored identity.
      if (data.changed && !sessionStorage.getItem(RELOAD_FLAG)) {
        sessionStorage.setItem(RELOAD_FLAG, "1");
        location.reload();
      } else if (!data.changed) {
        sessionStorage.removeItem(RELOAD_FLAG);
      }
    });
  }).catch(function () { /* offline or blocked: the cookie alone still works */ });
})();
